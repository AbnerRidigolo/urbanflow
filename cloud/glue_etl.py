"""Reference Glue entry point. Upload project wheel + this script only after cloud authorization."""
import sys
from awsglue.utils import getResolvedOptions
from pyspark.sql import SparkSession, functions as F
from urbanflow.etl import standardize

args = getResolvedOptions(sys.argv, ["MONTH", "BRONZE_URI", "SILVER_URI", "RUN_ID"])
spark = SparkSession.builder.getOrCreate()
spark.conf.set("spark.sql.session.timeZone", "UTC")
df = standardize(spark.read.parquet(args["BRONZE_URI"]), args["MONTH"]).cache()
total = df.count()
bad = df.filter(F.col("rejection_reason") != "")
rejected = bad.count()
version = args["SILVER_URI"].rstrip("/") + "/versions/" + args["RUN_ID"]
bad.write.mode("errorifexists").parquet(version + "/quarantine")
if not total or rejected/total > .05: raise ValueError("Quality gate failed; no catalog promotion")
df.filter(F.col("rejection_reason") == "").drop("rejection_reason").write.mode("errorifexists").parquet(version + "/trips")
# Promotion requires separately reviewed manifest/Catalog transaction adapter.
print({"input":total,"accepted":total-rejected,"rejected":rejected,"candidate":version})
