"""
Generator: data_cod
Rows: ~3M COD records (60% of 5M orders have COD)
1 record per order normally; adjustment records for failed collection
Output: data/raw/data_cod.parquet
Dependencies: data_shippingorder_now
"""
from pathlib import Path
import numpy as np
import pandas as pd

from config import COD_RATE, COD_AMOUNT_MEDIAN
from _dirty import flag_quality

COD_STATUS_WEIGHTS = {
    "collected":       0.72,   # tiền đã thu
    "pending":         0.15,   # chờ thu
    "failed":          0.08,   # không thu được
    "transferred":     0.05,   # đã chuyển về merchant
}

RECONCILE_STATUS = {
    "reconciled":      0.80,
    "pending":         0.15,
    "discrepancy":     0.05,
}


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    order_df = kwargs.get("order_df")
    if order_df is None:
        order_df = pd.read_parquet("data/raw/data_shippingorder_now.parquet",
                                   columns=["order_code", "cod_amount",
                                            "status", "created_date",
                                            "deliver_warehouse_id",
                                            "end_delivery_time"])

    # Filter chỉ order có COD
    cod_orders = order_df[order_df["cod_amount"].notna() & (order_df["cod_amount"] > 0)].copy()

    # Safety: nếu ít hơn expected thì vẫn ok
    n = len(cod_orders)
    if n == 0:
        return pd.DataFrame()

    cod_status_keys = list(COD_STATUS_WEIGHTS.keys())
    cod_status_prob = list(COD_STATUS_WEIGHTS.values())
    rec_status_keys = list(RECONCILE_STATUS.keys())
    rec_status_prob = list(RECONCILE_STATUS.values())

    # ── Base record ────────────────────────────────────────────────────────────
    cod_statuses    = rng.choice(cod_status_keys, size=n, p=cod_status_prob)
    rec_statuses    = rng.choice(rec_status_keys, size=n, p=rec_status_prob)

    # collected_amount: đúng amount nếu collected, 0 nếu failed, random% nếu pending
    collected_amounts = np.where(
        cod_statuses == "collected", cod_orders["cod_amount"].values,
        np.where(
            cod_statuses == "failed",   0,
            np.where(
                cod_statuses == "pending",
                (rng.uniform(0, 1, n) * cod_orders["cod_amount"].values),
                cod_orders["cod_amount"].values
            )
        )
    )

    # discrepancy_amount
    discrepancy_amounts = cod_orders["cod_amount"].values - collected_amounts

    # collect_time: sau end_delivery_time hoặc created_date
    base_ts = pd.to_datetime(
        cod_orders["end_delivery_time"].fillna(cod_orders["created_date"])
    )
    collect_offsets = pd.to_timedelta(rng.integers(0, 24 * 3, size=n), unit="h")
    collect_times   = base_ts + collect_offsets

    # transfer_time: 1-3 ngày sau collect
    transfer_offsets = pd.to_timedelta(rng.integers(24, 72, size=n), unit="h")
    transfer_times   = collect_times + transfer_offsets
    transfer_times   = pd.Series(
        np.where(cod_statuses == "transferred", transfer_times, pd.NaT),
        index=cod_orders.index,
    )

    df = pd.DataFrame({
        "cod_id":             np.arange(1, n + 1, dtype=np.int64),
        "order_code":         cod_orders["order_code"].values,
        "warehouse_id":       cod_orders["deliver_warehouse_id"].values,
        "cod_amount":         cod_orders["cod_amount"].values,
        "collected_amount":   collected_amounts,
        "discrepancy_amount": discrepancy_amounts,
        "cod_status":         cod_statuses,
        "reconcile_status":   rec_statuses,
        "collect_time":       collect_times.values,
        "transfer_time":      transfer_times.values,
        "dt":                 collect_times.dt.strftime("%Y-%m-%d").values,
        "_data_quality":      "clean",
    }, index=cod_orders.index).reset_index(drop=True)

    # ── Adjustment records (discrepancy rows) ──────────────────────────────────
    # ~5% discrepancy → thêm 1 adjustment record
    discrepancy_mask = (df["reconcile_status"] == "discrepancy") & (df["discrepancy_amount"].abs() > 1000)
    adj_rows = df[discrepancy_mask].copy()
    adj_rows["cod_id"] = np.arange(n + 1, n + 1 + len(adj_rows), dtype=np.int64)
    adj_rows["cod_status"]         = "adjustment"
    adj_rows["reconcile_status"]   = "pending"
    adj_rows["collected_amount"]   = adj_rows["discrepancy_amount"]
    adj_rows["discrepancy_amount"] = 0
    adj_rows["collect_time"]       = adj_rows["collect_time"] + pd.Timedelta(days=1)
    adj_rows["_data_quality"]      = "clean"

    df = pd.concat([df, adj_rows], ignore_index=True)
    n_total = len(df)

    heavy = pd.Series(False, index=df.index)
    light = pd.Series(False, index=df.index)

    # C1: 0.8% cod_amount NULL (heavy — thiếu key financial field)
    null_cod = pd.Series(rng.random(n_total) < 0.008, index=df.index)
    df.loc[null_cod, "cod_amount"] = None
    heavy |= null_cod

    # C2: 0.3% collected_amount âm (impossible — negative collection)
    neg_col = pd.Series(rng.random(n_total) < 0.003, index=df.index)
    df.loc[neg_col, "collected_amount"] = -abs(df.loc[neg_col, "collected_amount"])
    heavy |= neg_col

    # C3: 1.5% collect_time NULL (light — timestamp missing)
    null_ct = pd.Series(rng.random(n_total) < 0.015, index=df.index)
    df.loc[null_ct, "collect_time"] = pd.NaT
    light |= null_ct

    # C4: 0.5% reconcile_status deprecated value
    dep_rec = pd.Series(rng.random(n_total) < 0.005, index=df.index)
    df.loc[dep_rec, "reconcile_status"] = "manual_review"   # deprecated status
    light |= dep_rec

    df = flag_quality(df, heavy, light)
    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/data_cod.parquet")
    write(df, out)
    print(f"data_cod: {len(df):,} rows → {out}")
    print(df["cod_status"].value_counts(dropna=False).to_string())
    print(df["reconcile_status"].value_counts(dropna=False).to_string())
    print(df["_data_quality"].value_counts().to_string())
    total_cod   = df["cod_amount"].sum()
    total_col   = df["collected_amount"].sum()
    print(f"total COD: {total_cod:,.0f} VNĐ | collected: {total_col:,.0f} VNĐ | gap: {total_cod - total_col:,.0f}")
