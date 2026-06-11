"""
Shared constants for all generators.
All generators import from here — change once, applies everywhere.
"""

# ── Reproducibility ───────────────────────────────────────────────────────────
DEFAULT_SEED = 42

# ── Date range ────────────────────────────────────────────────────────────────
START_DATE = "2024-01-01"
END_DATE   = "2025-12-31"

# ── Volume targets ────────────────────────────────────────────────────────────
N_ORDERS       = 5_000_000
N_CLIENTS      = 50_000
N_SHIPPERS     = 1_500
N_WAREHOUSES_BC = 1_992   # BC bưu cục (KTC được hardcode riêng)

# ── Geographic skew (from/to province weight) ─────────────────────────────────
# province_id → relative weight.  IDs match dim_province hardcode.
GEO_SKEW = {
    # HCM 35%
    79: 0.35,
    # HN 25%
    1:  0.25,
    # 5 tỉnh lớn tiếp theo ~20% chia đều
    48: 0.04,  # Đà Nẵng
    92: 0.04,  # Cần Thơ
    74: 0.04,  # Bình Dương
    75: 0.04,  # Đồng Nai
    72: 0.04,  # Bà Rịa – Vũng Tàu
    # Còn lại 20% chia đều cho 57 tỉnh còn lại (handled in generator)
}
GEO_SKEW_OTHER_TOTAL = 0.20   # tổng weight cho các tỉnh không kể trên

# ── Seasonality multiplier (tháng 1–12) ──────────────────────────────────────
MONTHLY_MULTIPLIER = {
    1: 0.065, 2: 0.035, 3: 0.075, 4: 0.075,
    5: 0.080, 6: 0.080, 7: 0.080, 8: 0.085,
    9: 0.090, 10: 0.095, 11: 0.120, 12: 0.120,
}

# ── Day-of-week multiplier (0=Mon … 6=Sun) ───────────────────────────────────
DOW_MULTIPLIER = {0: 1.00, 1: 1.00, 2: 1.00, 3: 1.00,
                  4: 1.15, 5: 0.90, 6: 0.40}

# ── Service type mix ──────────────────────────────────────────────────────────
SERVICE_TYPE_WEIGHTS = {2: 0.60, 5: 0.40}   # 2=Nhanh, 5=Tiết kiệm

# ── Order type mix ────────────────────────────────────────────────────────────
TYPE_ORDER_WEIGHTS = {"deliver": 0.75, "return": 0.25}

# ── Phanloaivung mix ──────────────────────────────────────────────────────────
PHANLOAIVUNG_WEIGHTS = {"Nội Tỉnh": 0.30, "Nội Vùng": 0.40, "Liên Vùng": 0.30}

# ── SLA breach rate by vùng ───────────────────────────────────────────────────
SLA_BREACH_RATE = {"Nội Tỉnh": 0.04, "Nội Vùng": 0.085, "Liên Vùng": 0.125}

# ── COD ───────────────────────────────────────────────────────────────────────
COD_RATE = 0.60          # % đơn có COD
COD_AMOUNT_MEDIAN = 250_000   # VNĐ — median COD amount

# ── Client type mix ───────────────────────────────────────────────────────────
CLIENT_TYPE_WEIGHTS = {
    "TTS": 0.39, "SME": 0.31, "SHOPEE": 0.29,
    "LAZADA": 0.005, "TIKI": 0.005,
}
CLIENT_TIER_WEIGHTS = {
    "Bronze": 0.55, "Silver": 0.25, "Gold": 0.15, "Diamond": 0.05,
}

# ── Shipper performance tier ──────────────────────────────────────────────────
SHIPPER_TIER_WEIGHTS  = {"A": 0.25, "B": 0.50, "C": 0.25}
SHIPPER_TIER_SLA      = {"A": 0.95, "B": 0.85, "C": 0.70}

# ── Vehicle weights (kg) available ───────────────────────────────────────────
VEHICLE_WEIGHTS_KG = [500, 1100, 1900, 5000, 6500, 8000, 15000]

# ── Truck trip capacity ───────────────────────────────────────────────────────
TRUCK_PACKAGES_PER_TRIP = 20   # avg packages per truck trip (for trip_code grouping)

# ── Lastmile attempt distribution ────────────────────────────────────────────
# avg 1.5 attempt/order: ~75% giao lần 1 thành công, ~25% retry 1 lần
LASTMILE_ATTEMPT_P_RETRY = 0.25   # xác suất cần attempt thứ 2

# ── Failure reason distribution ──────────────────────────────────────────────
FAILURE_REASON_WEIGHTS = {
    "wrong_address": 0.40,
    "not_home":      0.30,
    "refused":       0.15,
    "damaged":       0.08,
    "other":         0.07,
}

# ── Order status weights (terminal / non-terminal) ───────────────────────────
# Đơn delivered ~72%, failed/return ~15%, in-progress ~13%
ORDER_STATUS_TERMINAL = {
    "delivered":        0.72,
    "return_to_sender": 0.10,
    "cancelled":        0.05,
}
ORDER_STATUS_ACTIVE = {
    "ready_to_pick": 0.04,
    "picking":       0.03,
    "in_transit":    0.04,
    "delivering":    0.02,
}

# ── KTC anchor (hardcoded từ GHN thực tế) ────────────────────────────────────
KTC_ANCHORS = [
    {"warehouse_id": 1001, "warehouse_name": "Kho Trung Chuyển Hưng Yên 01",      "region_shortname": "HY", "province_id": 33},
    {"warehouse_id": 1002, "warehouse_name": "Kho Trung Chuyển Hà Nội 02",        "region_shortname": "HN", "province_id": 1},
    {"warehouse_id": 1003, "warehouse_name": "Kho Trung Chuyển Hà Nội 03",        "region_shortname": "HN", "province_id": 1},
    {"warehouse_id": 1004, "warehouse_name": "Kho Trung Chuyển Dương Xá",         "region_shortname": "HN", "province_id": 1},
    {"warehouse_id": 1005, "warehouse_name": "Kho Trung Chuyển Hồ Chí Minh 01",   "region_shortname": "HCM", "province_id": 79},
    {"warehouse_id": 1006, "warehouse_name": "Kho Trung Chuyển Hồ Chí Minh 20",   "region_shortname": "HCM", "province_id": 79},
    {"warehouse_id": 1007, "warehouse_name": "Kho Trung Chuyển Cần Thơ",          "region_shortname": "CT",  "province_id": 92},
    {"warehouse_id": 1008, "warehouse_name": "Kho Trung Chuyển Đà Nẵng 01",       "region_shortname": "DN",  "province_id": 48},
]

# ── Warehouse type ────────────────────────────────────────────────────────────
WAREHOUSE_TYPE_KTC = "KTC"
WAREHOUSE_TYPE_BC  = "BC"

# ── Deliver shift ─────────────────────────────────────────────────────────────
DELIVER_SHIFT_WEIGHTS = {"Ca 1": 0.45, "Ca 2": 0.40, "Ca 3": 0.15}

# ── Created source ────────────────────────────────────────────────────────────
CREATED_SOURCE_WEIGHTS = {"api": 0.65, "web": 0.25, "mobile": 0.10}

# ── Package actions per warehouse stop ───────────────────────────────────────
# Mỗi kho mà đơn đi qua sẽ có 4 actions: receive → pack → export → unpack (kho tiếp)
# Kho đích cuối chỉ có receive → unpack (không pack/export tiếp)
ACTIONS_PER_TRANSIT_HOP = ["receive", "pack", "export"]   # kho trung gian
ACTIONS_FINAL_HOP       = ["receive", "unpack"]            # kho đích (BC giao)

# ── Trip code prefix ──────────────────────────────────────────────────────────
TRUCK_TRIP_CODE_PREFIX    = "T"    # vd T26052331WZUDIF
LASTMILE_TRIP_CODE_PREFIX = "L"    # vd L26052331WZUDIF — namespace riêng, KHÔNG join truck
