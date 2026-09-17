"""Fixture determinístico; números sintéticos nunca são apresentados como NYC real."""
from pathlib import Path
import numpy as np
import pandas as pd
from .storage import checksum, register_source


def create_fixture(root, months=("2024-01", "2024-02", "2024-03")):
    root = Path(root)
    rng = np.random.default_rng(42)
    records = []
    for month in months:
        start = pd.Timestamp(month + "-01")
        end = start + pd.offsets.MonthBegin(1)
        rows = []
        for hour in pd.date_range(start, end, freq="h", inclusive="left"):
            for zone, level in [(161, 3), (236, 2), (132, 1)]:
                demand = level + 3 * (8 <= hour.hour <= 20) + (hour.dayofweek < 5)
                for _ in range(rng.poisson(demand)):
                    pickup = hour + pd.Timedelta(seconds=int(rng.integers(0, 3500)))
                    rows.append((2, pickup, pickup + pd.Timedelta(minutes=int(rng.integers(3, 40))),
                                 1, float(rng.uniform(.3, 12)), zone, 161, 1,
                                 float(rng.uniform(8, 70))))
        # Preserve an exact duplicate: matching fields are not a business trip ID.
        rows.append(rows[0])
        # Known invalid row for reconciliation/quarantine.
        rows.append((2, start, start - pd.Timedelta(minutes=1), 1, -1., 999, 161, 1, 10.))
        df = pd.DataFrame(rows, columns=["VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime",
                                        "passenger_count", "trip_distance", "PULocationID", "DOLocationID", "payment_type", "total_amount"])
        dest = root / "bronze" / "synthetic" / month
        dest.mkdir(parents=True, exist_ok=True)
        tmp = dest / "fixture.tmp"
        df.to_parquet(tmp, index=False, coerce_timestamps="us")
        path = dest / f"{checksum(tmp)}.parquet"
        tmp.replace(path)
        records.append(register_source(root, path, month, "synthetic", {"generator": "urbanflow.fixture.v1", "seed": 42, "label": "SINTÉTICO"}, True))
    return records
