import json
from pathlib import Path
import pandas as pd
from .storage import atomic_json
from .warehouse import connect

def query(conn, text):
    result = conn.execute(text)
    return pd.DataFrame(result.fetchall(), columns=[c.name for c in result.description])

def records(df):
    return json.loads(df.to_json(orient="records",date_format="iso"))

def export_dashboard(project, report, config):
    dest = Path(project)/"artifacts"/report["kind"]
    dest.mkdir(parents=True,exist_ok=True)
    with connect() as conn:
        active = conn.execute("select table_schema from information_schema.view_table_usage where view_schema='analytics' and view_name='fct_trips'").fetchone()
        if not active or active[0] != report['warehouse']['gold_schema']:
            raise ValueError('Checkpoint não corresponde à Gold ativa; exportação bloqueada')
        count = conn.execute("select count(*) from analytics.fct_hourly").fetchone()[0]
        if count > config["max_ml_rows"]: raise MemoryError("Gold excede orçamento; selecione menos meses")
        hourly = query(conn,"select * from analytics.fct_hourly order by zone_id,hour_at")
        hourly["borough"] = hourly.borough.astype("category")
        zones = query(conn,"select a.*, z.zone_name from analytics.agg_zone a join analytics.dim_zone z using(zone_id) order by trips desc nulls last")
        hours = query(conn,"select * from analytics.agg_hour order by hour_at")
        heat = query(conn,"select extract(isodow from hour_at)::int as weekday,extract(hour from hour_at)::int as hour_of_day, sum(trips) trips from analytics.fct_hourly group by 1,2 order by 1,2").rename(columns={"hour_of_day":"hour"})
        for name in ["dim_zone","dim_hour","fct_hourly","agg_zone","agg_hour"]:
            with (dest/(name+".csv")).open("wb") as f:
                with conn.cursor().copy(f"copy (select * from analytics.{name}) to stdout with csv header") as copy:
                    for chunk in copy: f.write(bytes(chunk))
    summary = {"trips": int(hourly.trips.sum()), "total_usd": float(hourly.total_usd.sum()),
               "avg_duration_minutes": float(hourly.duration_minutes.sum()/max(1,hourly.trips.sum())),
               "input":sum(m["input"] for m in report["silver"]),"rejected":sum(m["rejected"] for m in report["silver"])}
    ml_report, predictions = None, []
    if report["kind"] != "public_sample":
        from .ml import train
        ml_report, pred = train(hourly,dest/"ml",report["kind"],config["max_ml_rows"],config["max_ml_memory_mb"])
        # A transaction preserves the previous predictions on load/reconciliation failure.
        with connect() as conn:
            conn.execute("""create table if not exists analytics.predictions (
                zone_id int, hour_at timestamp, borough text, trips double precision,
                baseline double precision, prediction double precision, cutoff timestamp,
                train_end_exclusive timestamp, absolute_error double precision, model_version text,
                primary key(zone_id,hour_at,model_version))""")
            conn.execute("delete from analytics.predictions")
            with conn.cursor().copy("copy analytics.predictions from stdin") as copy:
                for row in pred.itertuples(index=False,name=None): copy.write_row(tuple(None if pd.isna(v) else v for v in row))
        pred["date"] = pred.hour_at.dt.strftime("%Y-%m-%d")
        predictions = records(pred.groupby(["zone_id","date"],observed=True)[["trips","prediction","baseline","absolute_error"]].sum().reset_index())
    payload = {"kind":report["kind"],"created_at":report["created_at"],"months":report["months"],
               "summary":summary,"zones":records(zones),"hours":records(hours),"heatmap":records(heat),
               "ml":ml_report,"predictions":predictions,"quality":report["silver"],"warehouse":report["warehouse"]}
    atomic_json(dest/"dashboard.json",payload)
    atomic_json(Path(project)/"dashboard"/"data.json",payload)
