"""
Generator: dim_client
Rows: 50,000
Output: data/raw/dim_client.parquet
Dependencies: dim_district
"""
from pathlib import Path
import numpy as np
import pandas as pd
from faker import Faker

from config import (
    N_CLIENTS, CLIENT_TYPE_WEIGHTS, CLIENT_TIER_WEIGHTS,
    START_DATE,
)


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng  = np.random.default_rng(seed)
    fake = Faker("vi_VN")
    fake.seed_instance(seed)

    district_df = kwargs.get("district_df")
    if district_df is None:
        district_df = pd.read_parquet("data/raw/dim_district.parquet")

    n = N_CLIENTS

    # ── District assignment — theo geographic skew ─────────────────────────────
    # HCM (province 79) + HN (province 1) chiếm ~60% client
    prov_weights = np.where(
        district_df["province_id"] == 79, 3.5,
        np.where(district_df["province_id"] == 1, 2.5, 1.0)
    ).astype(float)
    prov_weights /= prov_weights.sum()
    dist_idx = rng.choice(len(district_df), size=n, p=prov_weights)
    districts = district_df.iloc[dist_idx]

    # ── Client type ────────────────────────────────────────────────────────────
    types  = list(CLIENT_TYPE_WEIGHTS.keys())
    t_prob = list(CLIENT_TYPE_WEIGHTS.values())
    client_types = rng.choice(types, size=n, p=t_prob)

    # ── Tier — SHOPEE/LAZADA/TIKI luôn Gold/Diamond ───────────────────────────
    tiers = []
    tier_keys = list(CLIENT_TIER_WEIGHTS.keys())
    tier_prob = list(CLIENT_TIER_WEIGHTS.values())
    platform_tiers = ["Gold", "Diamond"]
    for ct in client_types:
        if ct in ("SHOPEE", "LAZADA", "TIKI"):
            tiers.append(rng.choice(platform_tiers))
        else:
            tiers.append(rng.choice(tier_keys, p=tier_prob))

    # ── is_b2b — SME/LAZADA/TIKI/SHOPEE thường B2B ───────────────────────────
    is_b2b = np.array([
        ct in ("SME", "LAZADA", "TIKI", "SHOPEE") and rng.random() < 0.85
        or ct == "TTS" and rng.random() < 0.05
        for ct in client_types
    ])

    # ── Created date ──────────────────────────────────────────────────────────
    start_ts = pd.Timestamp("2018-01-01").timestamp()
    end_ts   = pd.Timestamp(START_DATE).timestamp()
    created_ts = rng.uniform(start_ts, end_ts, size=n)
    created_dates = pd.to_datetime(created_ts, unit="s").normalize().date

    df = pd.DataFrame({
        "client_id":    np.arange(1, n + 1, dtype=np.int64),
        "shop_id":      np.arange(100_001, 100_001 + n, dtype=np.int64),
        "client_type":  client_types,
        "province_id":  districts["province_id"].values,
        "district_id":  districts["district_id"].values,
        "is_b2b":       is_b2b,
        "created_date": created_dates,
        "tier":         tiers,
    })

    # ── Dirty inject ──────────────────────────────────────────────────────────
    # CL1: 1% client_type NULL
    null_mask = rng.random(n) < 0.01
    df.loc[null_mask, "client_type"] = None

    # _data_quality flag
    df["_data_quality"] = "clean"
    df.loc[null_mask, "_data_quality"] = "light_issue"

    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/dim_client.parquet")
    write(df, out)
    print(f"dim_client: {len(df)} rows → {out}")
    print(df["client_type"].value_counts(dropna=False).to_string())
