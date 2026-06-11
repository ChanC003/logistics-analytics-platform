"""
Generator: data_shipment
Rows: ~7.5M lastmile trips
Derives from data_shippingorder_now — avg 1.5 attempts/order (25% retry)
trip_code prefix = "L"  ← namespace riêng, KHÔNG join với data_transportation "T"
Output: data/raw/data_shipment.parquet
Dependencies: data_shippingorder_now, dim_shipper, dim_warehouse
"""
from pathlib import Path
import numpy as np
import pandas as pd

from config import (
    LASTMILE_TRIP_CODE_PREFIX, LASTMILE_ATTEMPT_P_RETRY,
    FAILURE_REASON_WEIGHTS, DELIVER_SHIFT_WEIGHTS,
)
from _dirty import flag_quality

_CHARS = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"))

_ATTEMPT_STATUS_MAP = {
    "delivered":        ("success", "delivered"),
    "return_to_sender": ("failed",  "return_to_sender"),
    "cancelled":        ("cancelled", "cancelled"),
    "in_transit":       ("in_progress", None),
    "delivering":       ("in_progress", None),
    "ready_to_pick":    ("pending", None),
    "picking":          ("pending", None),
}


def _gen_trip_codes(n: int, rng: np.random.Generator) -> np.ndarray:
    parts = rng.choice(_CHARS, size=(n, 14))
    codes = np.array([LASTMILE_TRIP_CODE_PREFIX + "".join(row) for row in parts])
    return codes


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    order_df = kwargs.get("order_df")
    if order_df is None:
        order_df = pd.read_parquet("data/raw/data_shippingorder_now.parquet",
                                   columns=["order_code", "status", "deliver_warehouse_id",
                                            "end_delivery_time", "created_date",
                                            "shipper_user_id", "deliver_shift",
                                            "is_sla_breach"])

    shipper_df = kwargs.get("shipper_df")
    if shipper_df is None:
        shipper_df = pd.read_parquet("data/raw/dim_shipper.parquet",
                                     columns=["shipper_id", "user_id"])

    wh_df = kwargs.get("warehouse_df")
    if wh_df is None:
        wh_df = pd.read_parquet("data/raw/dim_warehouse.parquet",
                                columns=["warehouse_id", "warehouse_type"])

    n_orders = len(order_df)
    user_ids = shipper_df["user_id"].values
    shipper_ids = shipper_df["shipper_id"].values

    shift_keys = list(DELIVER_SHIFT_WEIGHTS.keys())
    shift_prob = list(DELIVER_SHIFT_WEIGHTS.values())
    fail_keys  = list(FAILURE_REASON_WEIGHTS.keys())
    fail_prob  = list(FAILURE_REASON_WEIGHTS.values())

    rows = []

    for _, order in order_df.iterrows():
        status    = order["status"]
        order_cd  = order["order_code"]
        base_ts   = pd.Timestamp(order["end_delivery_time"] if not pd.isna(order.get("end_delivery_time")) else order["created_date"])

        # Số lần attempt: 75% 1 lần, 25% retry → 1 lần nữa
        n_attempts = 1
        if status == "delivered" and rng.random() < LASTMILE_ATTEMPT_P_RETRY:
            n_attempts = 2
        elif status == "return_to_sender" and rng.random() < 0.50:
            n_attempts = 2  # failed twice before return

        for attempt_no in range(1, n_attempts + 1):
            trip_cd = _gen_trip_codes(1, rng)[0]
            s_idx   = int(rng.integers(0, len(shipper_ids)))

            is_last = (attempt_no == n_attempts)
            if is_last:
                attempt_status = _ATTEMPT_STATUS_MAP.get(status, ("in_progress", None))[0]
                attempt_result = _ATTEMPT_STATUS_MAP.get(status, ("in_progress", None))[1]
            else:
                attempt_status = "failed"
                attempt_result = "retry"

            # Thời gian deliver
            days_offset = attempt_no - 1
            deliver_ts  = base_ts + pd.Timedelta(days=days_offset,
                                                  hours=int(rng.integers(7, 20)),
                                                  minutes=int(rng.integers(0, 60)))

            fail_reason = None
            if attempt_status == "failed":
                fail_reason = rng.choice(fail_keys, p=fail_prob)

            rows.append({
                "trip_code":          trip_cd,
                "order_code":         order_cd,
                "attempt_no":         attempt_no,
                "shipper_id":         int(shipper_ids[s_idx]),
                "shipper_user_id":    user_ids[s_idx],
                "deliver_warehouse_id": order.get("deliver_warehouse_id"),
                "deliver_shift":      rng.choice(shift_keys, p=shift_prob),
                "attempt_status":     attempt_status,
                "attempt_result":     attempt_result,
                "failure_reason":     fail_reason,
                "deliver_time":       deliver_ts,

                "dt":                 deliver_ts.strftime("%Y-%m-%d"),
                "_data_quality":      "clean",
            })

    df = pd.DataFrame(rows)

    n = len(df)
    heavy = pd.Series(False, index=df.index)
    light = pd.Series(False, index=df.index)

    # LM1: 0.8% deliver_warehouse_id NULL
    null_dwh = pd.Series(rng.random(n) < 0.008, index=df.index)
    df.loc[null_dwh, "deliver_warehouse_id"] = None
    light |= null_dwh

    # LM2: 0.5% failure_reason NULL trên attempt_status="failed" (thiếu lý do)
    failed_mask = df["attempt_status"] == "failed"
    null_fr = pd.Series(rng.random(n) < 0.005, index=df.index) & failed_mask
    df.loc[null_fr, "failure_reason"] = None
    heavy |= null_fr

    # LM3: 0.2% deliver_time < order created_date equivalent (time anomaly)
    time_anm = pd.Series(rng.random(n) < 0.002, index=df.index)
    df.loc[time_anm, "deliver_time"] = pd.Timestamp("2023-01-01")
    heavy |= time_anm

    df = flag_quality(df, heavy, light)
    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/data_shipment.parquet")
    write(df, out)
    print(f"data_shipment: {len(df):,} rows → {out}")
    print(df["attempt_status"].value_counts(dropna=False).to_string())
    print(df["_data_quality"].value_counts().to_string())
    print(f"avg attempts/order: {n_orders_expected := len(df[df['attempt_no'] == 1])}, total={len(df)}, ratio={len(df)/n_orders_expected:.2f}")
