"""Rolling one-hour-ahead backtest; monthly data does not support a live forecast claim."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from .storage import atomic_json

FEATURES = ["zone_id", "hour", "weekday", "lag_1", "lag_24", "lag_168", "mean_24", "mean_168"]


def features(hourly, max_rows=1500000, memory_mb=512):
    if len(hourly) > max_rows: raise MemoryError("Orçamento de linhas ML excedido")
    if hourly.memory_usage(deep=True).sum() * 8 > memory_mb * 1024**2:
        raise MemoryError("Orçamento de memória ML excedido (inclui temporários)")
    df = hourly.copy()
    df["hour_at"] = pd.to_datetime(df.hour_at)
    if df.duplicated(["zone_id", "hour_at"]).any(): raise ValueError("Hora/zona duplicada")
    # Keep wall-clock hours. Ambiguous/nonexistent DST hours are unknown, never guessed.
    local = pd.DatetimeIndex(df.hour_at).tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
    df.loc[~df.complete.astype(bool) | local.isna(), "trips"] = np.nan
    parts = []
    for zone, group in df.groupby("zone_id", sort=True):
        group = group.set_index("hour_at").sort_index()
        group = group.reindex(pd.date_range(group.index.min(), group.index.max(), freq="h"))
        group.index.name = "hour_at"
        group["zone_id"] = zone
        y = group.trips
        for lag in (1, 24, 168): group[f"lag_{lag}"] = y.shift(lag)
        for window in (24, 168): group[f"mean_{window}"] = y.shift(1).rolling(window, min_periods=window).mean()
        group["hour"], group["weekday"] = group.index.hour, group.index.dayofweek
        parts.append(group.reset_index())
    return pd.concat(parts, ignore_index=True)


def metrics(actual, predicted):
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if len(a) == 0 or not (np.isfinite(a).all() and np.isfinite(p).all()): raise ValueError("Métricas exigem pares finitos")
    error = np.abs(a-p)
    denominator = np.abs(a).sum()
    return {"mae": float(error.mean()), "wape": float(error.sum()/denominator) if denominator > 0 else None,
            "n": len(a), "actual_sum": float(denominator)}


def train(hourly, dest, kind, max_rows=1500000, memory_mb=512):
    if kind == "public_sample": raise ValueError("Amostra parcial não representa demanda; ML bloqueado")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    df = features(hourly, max_rows, memory_mb)
    valid = df.dropna(subset=FEATURES + ["trips"])
    times = sorted(valid.hour_at.unique())
    if len(times) < 168: raise ValueError("Histórico insuficiente após warmup de 168h")
    validation_start, test_start = pd.Timestamp(times[int(len(times)*.6)]), pd.Timestamp(times[int(len(times)*.8)])
    fit = valid[valid.hour_at < validation_start]
    val = valid[(valid.hour_at >= validation_start) & (valid.hour_at < test_start)]
    test = valid[valid.hour_at >= test_start]
    candidates = []
    for leaves in (7, 15):
        model = HistGradientBoostingRegressor(max_leaf_nodes=leaves, max_iter=80, learning_rate=.08,
                                             l2_regularization=1., random_state=42, early_stopping=False)
        model.fit(fit[FEATURES], fit.trips)
        candidates.append((metrics(val.trips, np.maximum(0, model.predict(val[FEATURES])))["mae"], leaves))
    _, leaves = min(candidates)
    final_train = valid[valid.hour_at < test_start]
    model = HistGradientBoostingRegressor(max_leaf_nodes=leaves, max_iter=80, learning_rate=.08,
                                         l2_regularization=1., random_state=42, early_stopping=False)
    model.fit(final_train[FEATURES], final_train.trips)
    pred = test[["zone_id", "hour_at", "borough", "trips"]].copy()
    pred["baseline"] = test.lag_168.values
    pred["prediction"] = np.maximum(0, model.predict(test[FEATURES]))
    pred["cutoff"] = pred.hour_at  # At the start of target hour, previous hour is complete in the simulation.
    pred["train_end_exclusive"] = test_start
    pred["absolute_error"] = (pred.prediction-pred.trips).abs()
    import joblib
    joblib.dump(model, dest / "model.joblib")
    version = hashlib.sha256((dest / "model.joblib").read_bytes()).hexdigest()
    pred["model_version"] = version
    pred.to_csv(dest / "predictions.csv", index=False)
    report = {"kind": kind, "evaluation": "simulação histórica rolling one-step; NÃO produção ao vivo",
              "train_end_exclusive": test_start.isoformat(), "validation_start": validation_start.isoformat(),
              "test_start": test_start.isoformat(), "test_end": str(test.hour_at.max()),
              "train_rows": len(final_train), "excluded_rows": len(df)-len(valid),
              "model_version": version, "selected_max_leaf_nodes": leaves,
              "baseline": metrics(pred.trips,pred.baseline), "model": metrics(pred.trips,pred.prediction),
              "by_borough": {str(k): {"model": metrics(g.trips,g.prediction), "baseline": metrics(g.trips,g.baseline)}
                             for k,g in pred.groupby("borough", observed=True)},
              "by_zone": {str(k): {"model": metrics(g.trips,g.prediction), "baseline": metrics(g.trips,g.baseline)}
                          for k,g in pred.groupby("zone_id")}}
    atomic_json(dest / "metrics.json", report)
    import mlflow
    mlflow.set_tracking_uri("sqlite:///" + (dest / "mlflow.db").resolve().as_posix())
    experiment = mlflow.get_experiment_by_name("urbanflow-"+kind)
    experiment_id = experiment.experiment_id if experiment else mlflow.create_experiment(
        "urbanflow-"+kind, artifact_location=(dest/"mlruns").resolve().as_uri())
    with mlflow.start_run(experiment_id=experiment_id):
        mlflow.log_params({"kind": kind, "model_version": version, "leaves": leaves, "test_start": str(test_start), "horizon_hours": 1})
        mlflow.log_metrics({"model_mae": report["model"]["mae"], "baseline_mae": report["baseline"]["mae"]})
        for name in ["model.joblib", "metrics.json", "predictions.csv"]: mlflow.log_artifact(str(dest/name))
    return report, pred
