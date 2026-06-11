"""
Generator: dim_shipper
Rows: 1,500
Output: data/raw/dim_shipper.parquet
Dependencies: dim_warehouse
"""
from pathlib import Path
import numpy as np
import pandas as pd

from config import N_SHIPPERS, SHIPPER_TIER_WEIGHTS, VEHICLE_WEIGHTS_KG, START_DATE


# Biển số xe pattern: <2 số><1 chữ>-<5 số>  vd 29H-37497
_PLATE_PREFIXES = [
    "29H", "30A", "30B", "30E", "30F", "30G", "30H", "30K", "30L", "30M",
    "51A", "51B", "51C", "51D", "51E", "51F", "51G", "51H", "51K",
    "43A", "43B", "43C", "92A", "65A", "66A", "75A", "75B",
]


def _gen_plate(rng: np.random.Generator) -> str:
    prefix = rng.choice(_PLATE_PREFIXES)
    number = rng.integers(10000, 99999)
    return f"{prefix}-{number}"


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    warehouse_df = kwargs.get("warehouse_df")
    if warehouse_df is None:
        warehouse_df = pd.read_parquet("data/raw/dim_warehouse.parquet")

    n = N_SHIPPERS

    # ── Assign shipper → warehouse (BC ưu tiên, KTC ít hơn) ──────────────────
    bc_ids  = warehouse_df[warehouse_df["warehouse_type"] == "BC"]["warehouse_id"].values
    ktc_ids = warehouse_df[warehouse_df["warehouse_type"] == "KTC"]["warehouse_id"].values
    all_wh  = np.concatenate([
        np.repeat(bc_ids,  3),   # BC weight 3x
        np.repeat(ktc_ids, 1),
    ])
    warehouse_ids = rng.choice(all_wh, size=n)

    # province từ warehouse
    wh_prov = warehouse_df.set_index("warehouse_id")["province_id"].to_dict()
    province_ids = np.array([wh_prov.get(int(w), 79) for w in warehouse_ids], dtype=np.int64)

    # ── Performance tier ──────────────────────────────────────────────────────
    tier_keys = list(SHIPPER_TIER_WEIGHTS.keys())
    tier_prob = list(SHIPPER_TIER_WEIGHTS.values())
    perf_tiers = rng.choice(tier_keys, size=n, p=tier_prob)

    # ── Vehicle weight ────────────────────────────────────────────────────────
    veh_weights = rng.choice(VEHICLE_WEIGHTS_KG, size=n)

    # ── Hire date ─────────────────────────────────────────────────────────────
    start_ts = pd.Timestamp("2019-01-01").timestamp()
    end_ts   = pd.Timestamp(START_DATE).timestamp()
    hire_ts  = rng.uniform(start_ts, end_ts, size=n)
    hire_dates = pd.to_datetime(hire_ts, unit="s").normalize().date

    # ── user_id — format GHN: chữ hoa 8 ký tự ────────────────────────────────
    chars = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"))
    user_ids = ["".join(rng.choice(chars, size=8)) for _ in range(n)]

    df = pd.DataFrame({
        "shipper_id":         np.arange(1, n + 1, dtype=np.int64),
        "user_id":            user_ids,
        "warehouse_id":       warehouse_ids.astype(np.int64),
        "province_id":        province_ids,
        "hire_date":          hire_dates,
        "is_active":          rng.random(n) < 0.92,   # 8% inactive
        "performance_tier":   perf_tiers,
        "truck_plate_number": [_gen_plate(rng) for _ in range(n)],
        "vehicle_weight_kg":  veh_weights.astype(np.int32),
    })

    # ── Dirty inject ──────────────────────────────────────────────────────────
    heavy_mask = np.zeros(n, dtype=bool)
    light_mask = np.zeros(n, dtype=bool)

    # SH1: 2% plate format sai (ABC-1234 thay vì 29H-37497)
    bad_plate_mask = rng.random(n) < 0.02
    df.loc[bad_plate_mask, "truck_plate_number"] = [
        f"{''.join(rng.choice(list('ABCDE'), 3))}-{rng.integers(1000,9999)}"
        for _ in range(bad_plate_mask.sum())
    ]
    light_mask |= bad_plate_mask

    # SH2: 4% vehicle_weight_kg NULL
    null_veh = rng.random(n) < 0.04
    df.loc[null_veh, "vehicle_weight_kg"] = None
    light_mask |= null_veh

    # SH3: 0.3% hire_date trong tương lai
    future_hire = rng.choice(np.where(~heavy_mask)[0],
                              size=max(1, int(n * 0.003)), replace=False)
    for i in future_hire:
        df.at[i, "hire_date"] = pd.Timestamp("2027-01-01").date()
    heavy_mask[future_hire] = True

    # SH4: 0.1% is_active=True nhưng hire_date tương lai (logic impossible)
    # subset of SH3 — already flagged heavy

    df["_data_quality"] = "clean"
    df.loc[heavy_mask, "_data_quality"] = "heavy_issue"
    df.loc[light_mask & ~heavy_mask, "_data_quality"] = "light_issue"

    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/dim_shipper.parquet")
    write(df, out)
    print(f"dim_shipper: {len(df)} rows → {out}")
    print(df["performance_tier"].value_counts().to_string())
    print(df["_data_quality"].value_counts().to_string())
