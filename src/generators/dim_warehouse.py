"""
Generator: dim_warehouse
Rows: 2,000 (8 KTC hardcode + 1,992 BC Faker)
Output: data/raw/dim_warehouse.parquet
Dependencies: dim_district
"""
from pathlib import Path
import numpy as np
import pandas as pd
from faker import Faker

from config import KTC_ANCHORS, WAREHOUSE_TYPE_KTC, WAREHOUSE_TYPE_BC, N_WAREHOUSES_BC

# Tọa độ tâm tỉnh (lat, lon) — dùng để sinh lat/lon BC gần đúng
PROVINCE_COORDS = {
    1:  (21.03, 105.85), 2:  (22.80, 104.98), 4:  (22.67, 106.25),
    6:  (22.14, 105.83), 8:  (21.82, 105.22), 10: (22.48, 103.97),
    11: (21.39, 103.02), 12: (22.39, 103.46), 14: (21.33, 103.91),
    15: (21.72, 104.91), 17: (20.68, 105.34), 19: (21.59, 105.85),
    20: (21.84, 106.76), 22: (21.00, 107.30), 24: (21.28, 106.20),
    25: (21.40, 105.22), 26: (21.36, 105.60), 27: (21.18, 106.07),
    30: (20.94, 106.33), 31: (20.85, 106.68), 33: (20.85, 106.02),
    34: (20.45, 106.34), 35: (20.58, 105.92), 36: (20.42, 106.17),
    37: (20.26, 105.97), 38: (19.81, 105.77), 40: (19.23, 104.92),
    42: (18.35, 105.89), 44: (17.48, 106.60), 45: (16.75, 107.19),
    46: (16.47, 107.60), 48: (16.07, 108.22), 49: (15.88, 108.34),
    51: (15.12, 108.79), 52: (13.78, 109.22), 54: (13.09, 109.30),
    56: (12.24, 109.19), 58: (11.57, 108.99), 60: (11.09, 108.07),
    62: (14.35, 108.00), 64: (13.98, 108.00), 66: (12.67, 108.05),
    67: (12.00, 107.69), 68: (11.95, 108.44), 70: (11.75, 106.72),
    72: (10.54, 107.24), 74: (11.08, 106.65), 75: (11.07, 107.18),
    77: (11.31, 106.10), 79: (10.82, 106.63), 80: (10.54, 106.41),
    82: (10.36, 106.36), 83: (10.24, 106.37), 84: (9.94, 106.34),
    86: (10.24, 105.97), 87: (10.49, 105.63), 89: (10.52, 105.13),
    91: (10.01, 105.08), 92: (10.03, 105.79), 93: (9.79, 105.46),
    94: (9.60, 105.97),  95: (9.29, 105.73),  96: (9.18, 105.15),
}


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng  = np.random.default_rng(seed)
    fake = Faker("vi_VN")
    fake.seed_instance(seed)

    district_df = kwargs.get("district_df")
    if district_df is None:
        district_df = pd.read_parquet("data/raw/dim_district.parquet")

    province_ids = district_df["province_id"].unique().tolist()

    rows = []

    # ── 8 KTC anchor (hardcode) ───────────────────────────────────────────────
    for ktc in KTC_ANCHORS:
        pid = ktc["province_id"]
        lat_c, lon_c = PROVINCE_COORDS.get(pid, (16.0, 106.0))
        rows.append({
            "warehouse_id":      ktc["warehouse_id"],
            "warehouse_name":    ktc["warehouse_name"],
            "warehouse_type":    WAREHOUSE_TYPE_KTC,
            "district_id":       None,
            "province_id":       pid,
            "province_name":     None,   # filled below
            "region_shortname":  ktc["region_shortname"],
            "region_fullname":   None,   # filled below
            "latitude":          round(lat_c + rng.uniform(-0.05, 0.05), 6),
            "longitude":         round(lon_c + rng.uniform(-0.05, 0.05), 6),
            "is_enabled":        True,
            "is_virtual":        False,
            "created_time":      pd.Timestamp("2018-01-01"),
        })

    # ── 1,992 BC — phân bổ theo tỉnh tỷ lệ với dân số / volume ───────────────
    # Trọng số đơn giản: HCM=200, HN=160, tỉnh lớn=30-60, còn lại=10-20
    BC_WEIGHT = {
        79: 200, 1: 160, 48: 60, 92: 50, 74: 55, 75: 55,
        31: 50, 72: 30, 38: 40, 40: 35,
    }
    default_w = 12
    weights = np.array([BC_WEIGHT.get(p, default_w) for p in province_ids], dtype=float)
    weights /= weights.sum()
    bc_per_province = np.round(weights * N_WAREHOUSES_BC).astype(int)
    # adjust rounding error
    diff = N_WAREHOUSES_BC - bc_per_province.sum()
    bc_per_province[np.argmax(bc_per_province)] += diff

    prov_info = district_df.groupby("province_id").first().reset_index()[
        ["province_id", "province_name"]
    ]
    prov_name_map = prov_info.set_index("province_id")["province_name"].to_dict()

    region_map = {}
    try:
        prov_df = pd.read_parquet("data/raw/dim_province.parquet")
        region_map = prov_df.set_index("province_id")[["region", "region_idx"]].to_dict("index")
    except FileNotFoundError:
        pass

    REGION_SHORT = {
        "Miền Bắc": "HN", "Miền Trung": "DN",
        "Tây Nguyên": "DN", "Miền Nam": "HCM",
    }

    warehouse_id = 2001   # BC IDs bắt đầu từ 2001
    for idx, province_id in enumerate(province_ids):
        n_bc = bc_per_province[idx]
        province_name = prov_name_map.get(province_id, f"Province {province_id}")
        region_full = region_map.get(province_id, {}).get("region", "Miền Nam")
        region_short = REGION_SHORT.get(region_full, "HCM")

        # districts của tỉnh này
        dist_ids = district_df[district_df["province_id"] == province_id]["district_id"].tolist()

        lat_c, lon_c = PROVINCE_COORDS.get(province_id, (16.0, 106.0))

        for _ in range(n_bc):
            dist_id = int(rng.choice(dist_ids))
            # dirty: 3% lat/lon = 0 (W1)
            if rng.random() < 0.03:
                lat, lon = 0.0, 0.0
            else:
                lat = round(lat_c + rng.uniform(-0.3, 0.3), 6)
                lon = round(lon_c + rng.uniform(-0.3, 0.3), 6)

            # dirty: 5% trailing whitespace trong tên (W3)
            name = f"Bưu Cục {province_name} {warehouse_id - 2000:04d}"
            if rng.random() < 0.05:
                name = name + " "

            rows.append({
                "warehouse_id":      warehouse_id,
                "warehouse_name":    name,
                "warehouse_type":    WAREHOUSE_TYPE_BC,
                "district_id":       dist_id,
                "province_id":       province_id,
                "province_name":     province_name,
                "region_shortname":  region_short,
                "region_fullname":   region_full,
                "latitude":          lat,
                "longitude":         lon,
                "is_enabled":        True,
                "is_virtual":        False,
                "created_time":      pd.Timestamp("2018-01-01") + pd.Timedelta(days=int(rng.integers(0, 1800))),
            })
            warehouse_id += 1

    df = pd.DataFrame(rows)

    # Backfill province_name / region_fullname cho KTC rows
    if region_map:
        for i, row in df[df["province_name"].isna()].iterrows():
            pid = row["province_id"]
            df.at[i, "province_name"]  = prov_name_map.get(pid, "")
            df.at[i, "region_fullname"] = region_map.get(pid, {}).get("region", "Miền Nam")

    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/dim_warehouse.parquet")
    write(df, out)
    ktc = (df["warehouse_type"] == "KTC").sum()
    bc  = (df["warehouse_type"] == "BC").sum()
    print(f"dim_warehouse: {len(df)} rows (KTC={ktc}, BC={bc}) → {out}")
