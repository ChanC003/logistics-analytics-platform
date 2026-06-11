"""
Generator: data_shippingorder_now
Rows: 5,000,000 (2M năm 2024 + 3M năm 2025)
Output: data/raw/data_shippingorder_now.parquet
Dependencies: dim_province, dim_district, dim_warehouse, dim_client, dim_shipper, dim_date
"""
from pathlib import Path
import numpy as np
import pandas as pd

from config import (
    N_ORDERS, MONTHLY_MULTIPLIER, DOW_MULTIPLIER,
    SERVICE_TYPE_WEIGHTS, TYPE_ORDER_WEIGHTS, PHANLOAIVUNG_WEIGHTS,
    SLA_BREACH_RATE, COD_RATE, COD_AMOUNT_MEDIAN,
    FAILURE_REASON_WEIGHTS, DELIVER_SHIFT_WEIGHTS,
    CREATED_SOURCE_WEIGHTS, ORDER_STATUS_TERMINAL, ORDER_STATUS_ACTIVE,
)
from _dirty import inject_nulls_seeded, inject_outliers, inject_duplicates, inject_enum_drift, flag_quality

# Order code: 8 ký tự uppercase
_CHARS = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))


_SLA_DAYS = {
    ("Nội Tỉnh", 2): 1, ("Nội Tỉnh", 5): 2,
    ("Nội Vùng", 2): 2, ("Nội Vùng", 5): 3,
    ("Liên Vùng", 2): 3, ("Liên Vùng", 5): 5,
}

def _get_year_rows():
    n = N_ORDERS
    return {2024: int(n * 0.4), 2025: n - int(n * 0.4)}


def _gen_order_codes(n: int, rng: np.random.Generator) -> np.ndarray:
    mat = rng.integers(0, 26, size=(n, 8))
    return np.array(["".join(_CHARS[row]) for row in mat])


def _assign_dates(year: int, n: int, rng: np.random.Generator) -> pd.DatetimeIndex:
    """Sinh ngày trong năm theo monthly + dow multiplier — fully vectorized."""
    # Bước 1: build toàn bộ ngày trong năm + weight tổng hợp monthly × dow
    all_days = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")
    day_weights = np.array([
        MONTHLY_MULTIPLIER[d.month] * DOW_MULTIPLIER[d.dayofweek]
        for d in all_days
    ], dtype=np.float64)
    day_weights /= day_weights.sum()

    # Bước 2: sample n ngày theo weight (vectorized)
    chosen_idx = rng.choice(len(all_days), size=n, p=day_weights)
    chosen_days = all_days[chosen_idx]

    # Bước 3: add random hour + minute
    hours   = rng.integers(6, 22, size=n).astype("timedelta64[h]")
    minutes = rng.integers(0, 60, size=n).astype("timedelta64[m]")
    return pd.DatetimeIndex(chosen_days) + hours + minutes


def _build_year(year: int, n: int, rng: np.random.Generator,
                district_df, warehouse_df, client_df, shipper_df) -> pd.DataFrame:

    # ── Lookup arrays ──────────────────────────────────────────────────────────
    dist_ids      = district_df["district_id"].values
    client_ids    = client_df["client_id"].values
    shop_ids      = client_df["shop_id"].values
    shipper_ids   = shipper_df["shipper_id"].values
    bc_ids        = warehouse_df[warehouse_df["warehouse_type"] == "BC"]["warehouse_id"].values
    all_wh_ids    = warehouse_df["warehouse_id"].values

    dist_prov = district_df.set_index("district_id")["province_id"].to_dict()
    wh_prov   = warehouse_df.set_index("warehouse_id")["province_id"].to_dict()

    # ── Generate clean base ────────────────────────────────────────────────────
    order_codes   = _gen_order_codes(n, rng)
    created_dates = _assign_dates(year, n, rng)
    dt            = created_dates.normalize().date   # partition key

    # Client
    c_idx     = rng.integers(0, len(client_ids), size=n)
    client_id = client_ids[c_idx]
    shop_id   = shop_ids[c_idx]

    # Districts — vectorized lookup
    from_dist = rng.choice(dist_ids, size=n)
    to_dist   = rng.choice(dist_ids, size=n)

    # Service type
    svc_keys = list(SERVICE_TYPE_WEIGHTS.keys())
    svc_prob = list(SERVICE_TYPE_WEIGHTS.values())
    service_type_id = rng.choice(svc_keys, size=n, p=svc_prob).astype(np.int64)

    # Weight (gram) — lognormal, median ~800g
    weight = np.exp(rng.normal(6.7, 0.9, size=n)).astype(np.int64)
    weight = np.clip(weight, 10, 30_000)
    # 40% làm tròn lên 500g gần nhất (human rounding)
    round_mask = rng.random(n) < 0.40
    weight[round_mask] = ((weight[round_mask] + 499) // 500) * 500

    length = rng.integers(5, 80, size=n).astype(np.int64)
    width  = rng.integers(5, 60, size=n).astype(np.int64)
    height = rng.integers(2, 50, size=n).astype(np.int64)
    # 15% khai thấp height
    low_h = rng.random(n) < 0.15
    height[low_h] = (height[low_h] * 0.5).astype(np.int64)
    converted_weight = np.maximum(weight, (length * width * height) // 6)

    # COD
    has_cod      = rng.random(n) < COD_RATE
    cod_amount   = np.where(has_cod,
                            np.exp(rng.normal(np.log(COD_AMOUNT_MEDIAN), 0.8, n)).astype(np.int64),
                            0)
    cod_amount   = np.round(cod_amount / 1000).astype(np.int64) * 1000   # làm tròn 1k

    insurance_value = (cod_amount * rng.uniform(0.5, 1.0, n)).astype(np.int64)

    # Warehouses
    pick_wh       = rng.choice(bc_ids, size=n)
    deliver_wh    = rng.choice(bc_ids, size=n)
    current_wh    = pick_wh.copy()
    return_wh     = rng.choice(bc_ids, size=n)
    pick_station  = pick_wh.copy()   # thường = pick_wh

    # Shippers
    pick_user     = rng.choice(shipper_ids, size=n)
    deliver_user  = rng.choice(shipper_ids, size=n)
    return_user   = rng.choice(shipper_ids, size=n)

    # Status
    all_statuses = {**ORDER_STATUS_TERMINAL, **ORDER_STATUS_ACTIVE}
    st_keys  = list(all_statuses.keys())
    st_prob  = np.array(list(all_statuses.values()))
    st_prob /= st_prob.sum()
    status   = rng.choice(st_keys, size=n, p=st_prob)

    # Failure reason — only for failed-path orders
    failure_fn_keys = list(FAILURE_REASON_WEIGHTS.keys())
    failure_fn_prob = list(FAILURE_REASON_WEIGHTS.values())
    failure_reason  = np.where(
        np.isin(status, ["return_to_sender"]),
        rng.choice(failure_fn_keys, size=n, p=failure_fn_prob),
        None
    )

    # SLA breach — dùng rate trung bình (phanloaivung do dbt tính sau)
    avg_breach_rate = sum(SLA_BREACH_RATE.values()) / len(SLA_BREACH_RATE)
    is_sla_breach = rng.random(n) < avg_breach_rate

    # type_order
    to_keys  = list(TYPE_ORDER_WEIGHTS.keys())
    to_prob  = list(TYPE_ORDER_WEIGHTS.values())
    type_order = rng.choice(to_keys, size=n, p=to_prob)

    # Deliver shift
    ds_keys  = list(DELIVER_SHIFT_WEIGHTS.keys())
    ds_prob  = list(DELIVER_SHIFT_WEIGHTS.values())
    deliver_shift = rng.choice(ds_keys, size=n, p=ds_prob)

    # Created source
    cs_keys = list(CREATED_SOURCE_WEIGHTS.keys())
    cs_prob = list(CREATED_SOURCE_WEIGHTS.values())
    created_source = rng.choice(cs_keys, size=n, p=cs_prob)

    # Timestamps
    end_pick_time       = created_dates + pd.to_timedelta(rng.integers(1, 6, n), unit="h")
    first_delivered_time = end_pick_time + pd.to_timedelta(rng.integers(12, 72, n), unit="h")
    end_delivery_time   = first_delivered_time + pd.to_timedelta(rng.integers(0, 24, n), unit="h")

    # date_id
    date_id = pd.Series(created_dates).dt.strftime("%Y%m%d").astype(int).values

    # Vectorized string fields
    from_names   = np.array([f"Nguoi gui {i}" for i in range(n)])  # ASCII, tránh encoding issue
    phone_digits = rng.integers(0, 10, size=(n, 7))
    from_phones  = np.array(["09" + "".join(map(str, row)) for row in phone_digits])
    to_phones    = np.array(["09" + "".join(map(str, row))
                             for row in rng.integers(0, 10, size=(n, 7))])
    from_wards   = np.array([f"W{v}" for v in rng.integers(10000, 99999, size=n)])
    to_wards     = np.array([f"W{v}" for v in rng.integers(10000, 99999, size=n)])
    contents     = np.array([f"Hang hoa {v}" for v in rng.integers(1, 100, size=n)])
    note_mask    = rng.random(n) < 0.30
    notes        = np.where(note_mask, "Goi truoc khi giao", None)

    df = pd.DataFrame({
        "order_code":            order_codes,
        "shop_id":               shop_id,
        "client_id":             client_id,
        "from_name":             from_names,
        "from_phone":            from_phones,
        "from_address":          np.array([f"Dia chi {i}" for i in range(n)]),
        "from_ward_code":        from_wards,
        "from_district_id":      from_dist,
        "to_phone":              to_phones,
        "to_ward_code":          to_wards,
        "to_district_id":        to_dist,
        "weight":                weight,
        "length":                length,
        "width":                 width,
        "height":                height,
        "converted_weight":      converted_weight,
        "service_type_id":       service_type_id,
        "service_id":            service_type_id * 10 + rng.integers(1, 5, n),
        "cod_amount":            cod_amount,
        "cod_collect_date":      np.where(has_cod, first_delivered_time.astype(str), None),
        "insurance_value":       insurance_value,
        "pick_station_id":       pick_station,
        "content":               contents,
        "note":                  notes,
        "created_source":        created_source,
        "created_date":          created_dates,
        "dt":                    dt,
        "date_id":               date_id,
        "status":                status,
        "pick_warehouse_id":     pick_wh,
        "deliver_warehouse_id":  deliver_wh,
        "current_warehouse_id":  current_wh,
        "return_warehouse_id":   return_wh,
        "deliver_shift":         deliver_shift,
        "pick_user":             pick_user,
        "deliver_user":          deliver_user,
        "return_user":           return_user,
        "end_pick_time":         end_pick_time,
        "first_delivered_time":  first_delivered_time,
        "end_delivery_time":     end_delivery_time,
        "cod_failed_amount":     np.zeros(n, dtype=np.int64),
        "cod_failed_collect_date": None,
        "is_b2b":                rng.random(n) < 0.15,
        "type_order":            type_order,
        "type_order_code":       np.array([f"TC{v}" for v in rng.integers(1, 10, size=n)]),
        "is_sla_breach":         is_sla_breach,
        "failure_reason":        failure_reason,
    })

    # ── Dirty inject ───────────────────────────────────────────────────────────
    heavy = pd.Series(False, index=df.index)
    light = pd.Series(False, index=df.index)

    # S1: 3% pick_user NULL
    df, m = inject_nulls_seeded(df, "pick_user", 0.03, rng)
    light |= m
    # S2: 8% deliver_user NULL khi in_transit
    in_transit = df["status"] == "in_transit"
    df, m = inject_nulls_seeded(df, "deliver_user", 0.08, rng, condition=in_transit)
    light |= m
    # S3: 1.5% failure_reason NULL khi status=return_to_sender (heavy)
    failed_cond = df["status"] == "return_to_sender"
    df, m = inject_nulls_seeded(df, "failure_reason", 0.015, rng, condition=failed_cond)
    heavy |= m
    # S4: 0.3% end_delivery_time < created_date
    s4 = pd.Series(rng.random(len(df)) < 0.003, index=df.index)
    df.loc[s4, "end_delivery_time"] = df.loc[s4, "created_date"] - pd.Timedelta(hours=5)
    heavy |= s4
    # S6: 0.8% weight = 0
    df = inject_outliers(df, "weight", [{"pct": 0.008, "type": "zero"}], rng)
    heavy |= (df["weight"] == 0)
    # S7: weight cực lớn outlier
    df = inject_outliers(df, "weight", [{"pct": 0.0005, "type": "range", "range": (200_000, 500_000)}], rng)
    light |= (df["weight"] > 30_000)
    # S8: 0.1% cod_amount âm
    df = inject_outliers(df, "cod_amount", [{"pct": 0.001, "type": "negative"}], rng)
    heavy |= (df["cod_amount"] < 0)
    # S9: 0.05% duplicate order_code
    df = inject_duplicates(df, "order_code", 0.0005, rng)
    heavy = heavy.reindex(df.index, fill_value=False)
    light = light.reindex(df.index, fill_value=False)
    heavy.iloc[len(heavy) - int(len(df) * 0.0005):] = True
    # S11: 0.6% deliver_warehouse_id NULL khi delivered
    delivered_cond = df["status"] == "delivered"
    df, m = inject_nulls_seeded(df, "deliver_warehouse_id", 0.006, rng, condition=delivered_cond)
    heavy |= m
    # S12: 2% is_sla_breach NULL
    df, m = inject_nulls_seeded(df, "is_sla_breach", 0.02, rng)
    light |= m
    # S13: 0.3% deprecated status
    df, m = inject_enum_drift(df, "status", ["DONE", "FINISH"], 0.003, rng)
    light |= m

    df = flag_quality(df, heavy, light)
    return df


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    district_df  = kwargs.get("district_df")
    warehouse_df = kwargs.get("warehouse_df")
    client_df    = kwargs.get("client_df")
    shipper_df   = kwargs.get("shipper_df")
    if district_df  is None: district_df  = pd.read_parquet("data/raw/dim_district.parquet")
    if warehouse_df is None: warehouse_df = pd.read_parquet("data/raw/dim_warehouse.parquet")
    if client_df    is None: client_df    = pd.read_parquet("data/raw/dim_client.parquet")
    if shipper_df   is None: shipper_df   = pd.read_parquet("data/raw/dim_shipper.parquet")

    frames = []
    for year, n in _get_year_rows().items():
        year_rng = np.random.default_rng(seed + year)   # deterministic per year
        frames.append(_build_year(year, n, year_rng,
                                   district_df, warehouse_df, client_df, shipper_df))
    return pd.concat(frames, ignore_index=True)


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/data_shippingorder_now.parquet")
    write(df, out)
    print(f"data_shippingorder_now: {len(df):,} rows → {out}")
    print(df["_data_quality"].value_counts().to_string())
    print(df["status"].value_counts().head(10).to_string())
