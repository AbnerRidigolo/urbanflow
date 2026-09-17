import argparse
import json
import logging
import os
from pathlib import Path
from .storage import atomic_json, read_json, run_lock, now


def main():
    p = argparse.ArgumentParser(description="UrbanFlow — pipeline gratuito local")
    p.add_argument("command", choices=["fixture", "ingest", "etl", "run", "export", "serve"])
    p.add_argument("--data", default="data")
    p.add_argument("--kind", choices=["synthetic", "public_sample", "public_full"], default="synthetic")
    p.add_argument("--months", nargs="+")
    p.add_argument("--full", action="store_true")
    p.add_argument("--max-mb", type=int, default=16)
    p.add_argument("--port", type=int, default=8080)
    args = p.parse_args()
    project = Path(os.getenv("URBANFLOW_PROJECT", str(Path.cwd() if (Path.cwd()/"config.json").exists() else Path(__file__).resolve().parents[2])))
    config = read_json(project / "config.json")
    os.environ.setdefault("SPARK_MASTER", config["spark_master"])
    os.environ.setdefault("SPARK_DRIVER_MEMORY", config["spark_driver_memory"])
    months = args.months or config["months"]
    root = Path(args.data).resolve()
    if args.command == "serve":
        from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
        from functools import partial
        ThreadingHTTPServer(("127.0.0.1", args.port), partial(SimpleHTTPRequestHandler, directory=str(project/"dashboard"))).serve_forever()
        return
    root.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=root/"pipeline.log",level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    logging.info("start command=%s kind=%s months=%s",args.command,args.kind,months)
    try:
        with run_lock(root):
            if args.command == "export":
                from .export import export_dashboard
                report = read_json(project/"artifacts"/"warehouse_checkpoint.json")
                export_dashboard(project,report,config)
                atomic_json(project/"artifacts"/"last_run.json", report)
                print("Exportação, ML e painel concluídos"); return
            if args.command == "fixture":
                from .fixture import create_fixture
                print(json.dumps(create_fixture(root,months),indent=2)); return
            if args.command == "ingest":
                from .ingest import ingest, zones
                zones(root)
                for month in months: print(json.dumps(ingest(root,month,args.max_mb*1024**2,args.full),indent=2))
                return
            from .etl import spark_session, transform
            sources = [read_json(root/"bronze"/args.kind/m/"current.json") for m in months]
            spark = spark_session()
            try: silver = [transform(root,s,spark,config["max_reject_ratio"]) for s in sources]
            finally: spark.stop()
            if args.command == "etl": print(json.dumps(silver,indent=2)); return
            from .warehouse import build, connect
            warehouse = build(project,silver,root/"reference"/"taxi_zone_lookup.csv")
            from .export import export_dashboard
            report = {"created_at": now(), "kind": args.kind, "months": months, "silver": silver, "warehouse": warehouse}
            atomic_json(project/"artifacts"/"warehouse_checkpoint.json", report)
            export_dashboard(project,report,config)
            atomic_json(project/"artifacts"/"last_run.json", report)
            print(json.dumps({"status":"passed", "kind":args.kind,"warehouse":warehouse},indent=2))
    except Exception:
        logging.exception("pipeline_failed")
        raise


if __name__ == "__main__": main()
