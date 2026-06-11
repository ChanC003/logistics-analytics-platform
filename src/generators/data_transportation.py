"""
Generator: data_transportation
Rows: ~500k truck trips
Trip derives from export events in data_inside_history.
Output: data/raw/data_transportation.parquet
Dependencies: data_inside_history (export rows), dim_warehouse, dim_shipper
"""
from pathlib import Path
import numpy as np
import pandas as pd

from config import TRUCK_TRIP_CODE_PREFIX, KTC_ANCHORS
from _dirty import flag_quality

_KTC_IDS = {k["warehouse_id"] for k in KTC_ANCHORS}
_CHARS   = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"))


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    inside_df = kwargs.get("inside_df")
    if inside_df is None:
        inside_df = pd.read_parquet("data/raw/data_inside_history.parquet",
                                    columns=["trip_code", "action_category",
                                             "warehouse_id", "to_warehouse_id",
                                             "action_time"])

    wh_df = kwargs.get("warehouse_df")
    if wh_df is None:
        wh_df = pd.read_parquet("data/raw/dim_warehouse.parquet",
                                columns=["warehouse_id", "warehouse_type", "province_id"])

    shipper_df = kwargs.get("shipper_df")
    if shipper_df is None:
        shipper_df = pd.read_parquet("data/raw/dim_shipper.parquet",
                                     columns=["shipper_id", "truck_plate_number",
                                              "vehicle_weight_kg", "warehouse_id"])

    # ── Aggregate export events by trip_code ──────────────────────────────────
    export_rows = inside_df[
        (inside_df["action_category"] == "export") &
        (inside_df["trip_code"].notna())
    ].copy()

    if len(export_rows) == 0:
        return pd.DataFrame()

    # trip_code → earliest action_time, từ warehouse, tới warehouse, package count
    trip_grp = (
        export_rows
        .groupby("trip_code")
        .agg(
            departure_time=("action_time", "min"),
            from_warehouse_id=("warehouse_id", "first"),
            to_warehouse_id=("to_warehouse_id", "first"),
            n_packages=("trip_code", "count"),
        )
        .reset_index()
    )

    # Filter: chỉ trip_code bắt đầu bằng "T" (truck trips)
    trip_grp = trip_grp[trip_grp["trip_code"].str.startswith(TRUCK_TRIP_CODE_PREFIX)]

    n = len(trip_grp)

    # ── Assign driver (shipper) ─────────────────────────────────────────────────
    # Shipper tại from_warehouse nếu có, fallback random
    wh_shippers = (
        shipper_df
        .groupby("warehouse_id")["shipper_id"]
        .apply(list)
        .to_dict()
    )
    driver_ids = []
    for _, row in trip_grp.iterrows():
        wh = int(row["from_warehouse_id"]) if not pd.isna(row["from_warehouse_id"]) else 0
        pool = wh_shippers.get(wh, shipper_df["shipper_id"].tolist())
        driver_ids.append(int(rng.choice(pool)))

    # Plates from matched shipper
    shipper_plate = shipper_df.set_index("shipper_id")["truck_plate_number"].to_dict()
    plates = [shipper_plate.get(d, "UNKNOWN") for d in driver_ids]

    # ── Arrival time: departure + travel hours ─────────────────────────────────
    # Nội Tỉnh ~2-4h, Nội Vùng ~4-8h, Liên Vùng ~8-20h
    # Tính nhanh: cùng province → short, khác province → long
    wh_prov = wh_df.set_index("warehouse_id")["province_id"].to_dict()
    travel_hours = []
    for _, row in trip_grp.iterrows():
        fp = wh_prov.get(int(row["from_warehouse_id"] or 0), 0)
        tp = wh_prov.get(int(row["to_warehouse_id"]   or 0), 0)
        if fp == tp:
            h = int(rng.integers(2, 5))
        elif fp in (1, 79) or tp in (1, 79):
            h = int(rng.integers(4, 9))
        else:
            h = int(rng.integers(8, 21))
        travel_hours.append(h)

    departure_times = pd.to_datetime(trip_grp["departure_time"])
    arrival_times   = departure_times + pd.to_timedelta(travel_hours, unit="h")

    # ── Vehicle weight (from shipper) ──────────────────────────────────────────
    shipper_veh = shipper_df.set_index("shipper_id")["vehicle_weight_kg"].to_dict()
    vehicle_weights = [shipper_veh.get(d, None) for d in driver_ids]

    df = pd.DataFrame({
        "trip_code":         trip_grp["trip_code"].values,
        "from_warehouse_id": trip_grp["from_warehouse_id"].values,
        "to_warehouse_id":   trip_grp["to_warehouse_id"].values,
        "departure_time":    departure_times.values,
        "arrival_time":      arrival_times.values,
        "driver_id":         driver_ids,
        "truck_plate_number": plates,
        "vehicle_weight_kg": vehicle_weights,
        "n_packages":        trip_grp["n_packages"].values,
        "dt":                departure_times.dt.strftime("%Y-%m-%d").values,
    })

    # ── Dirty inject ──────────────────────────────────────────────────────────
    heavy = pd.Series(False, index=df.index)
    light = pd.Series(False, index=df.index)

    # TR1: 0.5% arrival_time < departure_time (time travel)
    time_err = pd.Series(rng.random(n) < 0.005, index=df.index)
    df.loc[time_err, "arrival_time"] = df.loc[time_err, "departure_time"] - pd.Timedelta(hours=1)
    heavy |= time_err

    # TR2: 2% vehicle_weight_kg NULL
    null_vw = pd.Series(rng.random(n) < 0.02, index=df.index)
    df.loc[null_vw, "vehicle_weight_kg"] = None
    light |= null_vw

    # TR3: 0.3% from_warehouse_id = to_warehouse_id (same-warehouse trip)
    same_wh = pd.Series(rng.random(n) < 0.003, index=df.index)
    df["to_warehouse_id"] = df["to_warehouse_id"].astype(object)
    df.loc[same_wh, "to_warehouse_id"] = df.loc[same_wh, "from_warehouse_id"].values
    light |= same_wh

    df = flag_quality(df, heavy, light)
    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/data_transportation.parquet")
    write(df, out)
    print(f"data_transportation: {len(df):,} rows → {out}")
    print(df["_data_quality"].value_counts().to_string())
    print(f"avg packages/trip: {df['n_packages'].mean():.1f}")
