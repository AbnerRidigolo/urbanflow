"""ETL: regras Spark, quarentena e promoção por ponteiro de versão imutável."""
import os
import sys
from pathlib import Path
from uuid import uuid4
from .storage import atomic_json, checksum, now, read_json

RULE_VERSION = "silver-v1"


def spark_session():
    from pyspark.sql import SparkSession
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    return (SparkSession.builder.master(os.getenv("SPARK_MASTER", "local[2]"))
            .appName("UrbanFlow-ETL").config("spark.ui.enabled", "false")
            .config("spark.driver.memory", os.getenv("SPARK_DRIVER_MEMORY", "1g"))
            .config("spark.driver.host", "127.0.0.1")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.sql.parquet.enableVectorizedReader", "false")
            .getOrCreate())


def standardize(df, month):
    from pyspark.sql import functions as F
    mapping = {"tpep_pickup_datetime": ("pickup_at", "timestamp_ntz"),
               "tpep_dropoff_datetime": ("dropoff_at", "timestamp_ntz"),
               "PULocationID": ("pickup_zone_id", "int"), "DOLocationID": ("dropoff_zone_id", "int"),
               "trip_distance": ("distance_miles", "double"), "total_amount": ("total_usd", "double"),
               "passenger_count": ("passengers", "int"), "payment_type": ("payment_type", "int")}
    missing = set(mapping) - set(df.columns)
    if missing: raise ValueError(f"Schema crítico ausente: {sorted(missing)}")
    df = df.select(*[F.col(k).cast(t).alias(v) for k, (v, t) in mapping.items()])
    df = df.withColumn("duration_minutes", (F.unix_timestamp("dropoff_at") - F.unix_timestamp("pickup_at")) / 60)
    checks = {
        "timestamp_invalid": F.col("pickup_at").isNull() | F.col("dropoff_at").isNull(),
        "outside_partition": F.date_format("pickup_at", "yyyy-MM") != month,
        "duration_invalid": (F.col("duration_minutes") <= 0) | (F.col("duration_minutes") > 1440),
        "zone_invalid": ~F.col("pickup_zone_id").between(1, 265) | ~F.col("dropoff_zone_id").between(1, 265),
        "distance_invalid": F.col("distance_miles").isNull() | F.isnan("distance_miles") | ~F.col("distance_miles").between(0, 500),
        "amount_invalid": F.col("total_usd").isNull() | F.isnan("total_usd") | ~F.col("total_usd").between(-1000, 10000),
    }
    # Null zones must not silently pass three-valued SQL predicates.
    checks["zone_invalid"] = F.coalesce(checks["zone_invalid"], F.lit(True))
    df = df.withColumn("rejection_reason", F.concat_ws("|", *[F.when(c, F.lit(k)) for k, c in checks.items()]))
    return df.withColumn("source_month", F.lit(month))


def write_parquet(df, path):
    """Bounded batches; Windows avoids unmaintained third-party winutils binaries."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from pyspark.sql.pandas.types import to_arrow_schema
    schema = to_arrow_schema(df.schema)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pq.ParquetWriter(path, schema) as writer:
        batch = []
        # toLocalIterator materializes ONE Spark partition on the JVM: bound that
        # partition too, not only the Python/Arrow batch.
        for row in df.repartition(32).toLocalIterator():
            batch.append(row.asDict())
            if len(batch) == 10000:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                batch.clear()
        if batch: writer.write_table(pa.Table.from_pylist(batch, schema=schema))


def transform(root, source, spark, max_reject_ratio=.05):
    root = Path(root)
    if checksum(source["path"]) != source["sha256"]: raise ValueError("Checksum Bronze divergente")
    dest = root / "silver" / source["kind"] / source["partition"]
    pointer = dest / "current.json"
    if pointer.exists():
        old = read_json(pointer)
        if old["source_sha256"] == source["sha256"] and old["rules"] == RULE_VERSION:
            if checksum(old["path"]) == old["sha256"]: return old
    version = dest / uuid4().hex
    version.mkdir(parents=True)
    df = standardize(spark.read.parquet(source["path"]), source["partition"]).cache()
    from pyspark.sql import functions as F
    counts = {r["rejection_reason"]: r["count"] for r in df.groupBy("rejection_reason").count().collect()}
    accepted = counts.get("", 0)
    total = sum(counts.values())
    rejected = total - accepted
    report = {"input": total, "accepted": accepted, "rejected": rejected,
              "reasons": counts, "passed": total > 0 and accepted > 0 and rejected / total <= max_reject_ratio,
              "threshold": max_reject_ratio, "created_at": now()}
    write_parquet(df.filter(F.col("rejection_reason") != ""), version / "quarantine.parquet")
    atomic_json(version / "quality.json", report)
    try:
        if not report["passed"]: raise ValueError(f"Gate de qualidade reprovado: {report}")
        path = version / "trips.parquet"
        write_parquet(df.filter(F.col("rejection_reason") == "").drop("rejection_reason"), path)
        import pyarrow.parquet as pq
        if pq.ParquetFile(path).metadata.num_rows != accepted: raise ValueError("Reconciliação Silver falhou")
        result = {**report, "source_sha256": source["sha256"], "sha256": checksum(path),
                  "path": str(path.resolve()), "partition": source["partition"], "kind": source["kind"],
                  "complete": source["complete"], "rules": RULE_VERSION}
        atomic_json(version / "manifest.json", result)
        atomic_json(pointer, result)
        return result
    finally:
        df.unpersist()
