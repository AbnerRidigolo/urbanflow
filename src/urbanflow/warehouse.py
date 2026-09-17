"""Load Silver, run ELT/dbt in isolated schemas, promote views after dbt tests."""
import csv
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
import pyarrow.parquet as pq
from .storage import checksum

MODELS = ["dim_zone", "dim_hour", "fct_trips", "fct_hourly", "agg_zone", "agg_hour"]


def connect():
    return psycopg.connect(host=os.getenv("PGHOST", "127.0.0.1"), port=os.getenv("PGPORT", "55432"),
                           user=os.getenv("PGUSER", "urbanflow"), password=os.getenv("PGPASSWORD", "urbanflow_local_only"),
                           dbname=os.getenv("PGDATABASE", "urbanflow"))


def build(project, manifests, zones_path):
    stage, gold = "uf_stage_" + uuid4().hex[:10], "uf_gold_" + uuid4().hex[:10]
    if len({m["kind"] for m in manifests}) != 1: raise ValueError("Não misturar sintético, parcial e completo")
    if len({m["partition"] for m in manifests}) != len(manifests): raise ValueError("Partição duplicada")
    with connect() as conn:
        conn.execute(sql.SQL("create schema {} ").format(sql.Identifier(stage)))
        conn.execute(sql.SQL("set search_path to {} ").format(sql.Identifier(stage)))
        conn.execute("""create table trips(pickup_at timestamp,dropoff_at timestamp,pickup_zone_id int,
            dropoff_zone_id int,distance_miles double precision,total_usd double precision,
            passengers int,payment_type int,duration_minutes double precision,source_month text)""")
        conn.execute("create table coverage(source_month text primary key,complete boolean)")
        for m in manifests:
            if not m["passed"] or checksum(m["path"]) != m["sha256"]: raise ValueError("Silver não validada")
            with conn.cursor().copy("copy trips from stdin") as cp:
                for batch in pq.ParquetFile(m["path"]).iter_batches(batch_size=10000):
                    for row in zip(*[c.to_pylist() for c in batch.columns]): cp.write_row(row)
            conn.execute("insert into coverage values (%s,%s)", (m["partition"], m["complete"]))
        count = conn.execute("select count(*) from trips").fetchone()[0]
        if count != sum(m["accepted"] for m in manifests): raise ValueError("Reconciliação COPY falhou")
        conn.execute("create table zones(zone_id int primary key,borough text,zone_name text,service_zone text)")
        with open(zones_path, encoding="utf-8-sig") as f:
            with conn.cursor().copy("copy zones from stdin") as cp:
                for r in csv.DictReader(f): cp.write_row((int(r["LocationID"]),r["Borough"],r["Zone"],r["service_zone"]))
    env = {**os.environ, "UF_STAGE_SCHEMA": stage, "UF_GOLD_SCHEMA": gold, "DBT_SEND_ANONYMOUS_USAGE_STATS": "false"}
    dbt = Path(sys.executable).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    logdir = Path(project) / "artifacts" / "dbt" / gold
    logdir.mkdir(parents=True, exist_ok=True)
    command = [str(dbt), "build", "--project-dir", str(Path(project)/"dbt"), "--profiles-dir", str(Path(project)/"dbt"),
               "--target-path", str(logdir.resolve()), "--log-path", str(logdir.resolve())]
    proc = subprocess.run(command, env=env, text=True, capture_output=True)
    (logdir / "console.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode: raise RuntimeError(f"dbt build reprovado; analytics anterior preservado: {logdir}")
    with connect() as conn:
        conn.execute("create schema if not exists analytics")
        for model in MODELS:
            conn.execute(sql.SQL("create or replace view analytics.{} as select * from {}.{}").format(
                sql.Identifier(model), sql.Identifier(gold), sql.Identifier(model)))
    return {"stage_schema": stage, "gold_schema": gold, "loaded_rows": count, "dbt_passed": True}
