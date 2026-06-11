# Data Quality Strategy — Synthetic Generator

Blueprint cho dirty data injection trong `src/generators/`. Mỗi issue được classify theo
**mức độ nặng** (phá schema / logic / nghiệp vụ) và **tỷ lệ** (% rows bị ảnh hưởng).

---

## 1. Taxonomy

```
HEAVY (nặng) — làm sai kết quả nếu không xử lý trước khi load
  ├── NULL bắt buộc
  ├── Duplicate PK / order_code
  ├── FK trỏ vào ID không tồn tại (orphan)
  ├── Logic impossible (end_time < start_time, weight < 0)
  └── Type mismatch (số lưu dạng string có ký tự lạ)

LIGHT (nhẹ) — gây noise / bias nhưng load vẫn được
  ├── NULL optional field
  ├── Whitespace / mixed-case / dấu phụ thừa
  ├── Outlier hợp lệ nhưng cực đoan
  ├── Enum giá trị cũ / deprecated
  └── Timestamp ở timezone sai (naive vs aware)

DRIFT / ANOMALY — pattern bất thường, dùng để test dashboard alert
  ├── Volume spike / drop đột ngột
  ├── KTC outlier (breach rate cao bất thường)
  └── Shipper COD discrepancy liên tục
```

---

## 2. Dirty issues theo bảng

### 2.1 `data_shippingorder_now` — nguồn dirty chính

| # | Issue | Loại | Tỷ lệ | Column | Mô tả |
|---|---|---|---|---|---|
| S1 | NULL pick_user | LIGHT | 3% | `pick_user` | Đơn chưa assign shipper lấy |
| S2 | NULL deliver_user | LIGHT | 8% | `deliver_user` | Đơn đang in_transit chưa assign giao |
| S3 | NULL failure_reason khi status=failed | HEAVY | 1.5% | `failure_reason` | Giao thất bại nhưng không ghi lý do |
| S4 | end_delivery_time < created_date | HEAVY | 0.3% | timestamps | Clock skew — hệ thống ghi ngược |
| S5 | first_delivered_time > end_delivery_time | HEAVY | 0.2% | timestamps | Event ordering sai |
| S6 | weight = 0 | HEAVY | 0.8% | `weight` | Nhân viên không cân, điền 0 |
| S7 | weight cực lớn (> 500kg = 500,000g) | LIGHT/OUTLIER | 0.05% | `weight` | Hàng freight nhập sai đơn vị (kg thay vì gram) |
| S8 | cod_amount âm | HEAVY | 0.1% | `cod_amount` | Bug hệ thống khi điều chỉnh |
| S9 | order_code duplicate | HEAVY | 0.05% | `order_code` | Retry tạo đơn bị double-insert |
| S10 | from_district_id = to_district_id nhưng phanloaivung = 'Liên Vùng' | HEAVY | 0.4% | dims | Inconsistency phân loại vùng |
| S11 | deliver_warehouse_id NULL khi status = delivered | HEAVY | 0.6% | `deliver_warehouse_id` | Thiếu warehouse tracking |
| S12 | is_sla_breach = NULL (không tính được) | LIGHT | 2% | `is_sla_breach` | Đơn thiếu SLA reference |
| S13 | Giá trị status cũ / deprecated | LIGHT | 0.3% | `status` | `"DONE"` thay vì `"delivered"` — từ migration cũ |
| S14 | insurance_value > declared_value (logic impossible) | HEAVY | 0.2% | dims | Bảo hiểm cao hơn giá trị hàng |

### 2.2 `data_inside_history` (package action events)

| # | Issue | Loại | Tỷ lệ | Mô tả |
|---|---|---|---|---|
| E1 | action_time trùng nhau trên 1 package+order | HEAVY | 0.5% | Ghi double event cùng giây |
| E2 | action_category = NULL | HEAVY | 1% | Thiếu phân loại hành động — không xác định được bước nào trong vòng đời |
| E3 | Thiếu event `receive` đầu tiên của package | HEAVY | 0.3% | Package không có event nhập kho khởi tạo |
| E4 | Event sau `unpack` vẫn tiếp tục trên cùng package_code | HEAVY | 0.4% | package_code đã kết thúc nhưng vẫn có action tiếp |
| E5 | warehouse_id NULL | LIGHT | 5% | Kho không tracking — event từ shipper app offline |
| E6 | Gap > 7 ngày giữa 2 action liên tiếp trên 1 package | LIGHT/OUTLIER | 1.5% | Kiện bị "mất" trong hệ thống rồi resurface |

### 2.3 `data_cod`

| # | Issue | Loại | Tỷ lệ | Mô tả |
|---|---|---|---|---|
| C1 | cod_collected > cod_amount × 1.05 | HEAVY | 0.3% | Thu nhiều hơn phải thu >5% — suspect gian lận |
| C2 | recon_status = 'matched' nhưng discrepancy ≠ 0 | HEAVY | 0.5% | Label mismatch |
| C3 | Đơn không COD (cod_amount=0) nhưng có row trong bảng | LIGHT | 2% | Ghi nhầm |
| C4 | settled_at < recon_month | HEAVY | 0.2% | Settle trước khi tháng đối soát bắt đầu |
| C5 | Cùng order_code xuất hiện 2 lần trong cùng recon_month | HEAVY | 0.1% | Double reconciliation |

### 2.4 `dim_warehouse`

| # | Issue | Loại | Tỷ lệ | Mô tả |
|---|---|---|---|---|
| W1 | latitude / longitude = 0,0 | HEAVY | 3% | Null Island — chưa điền tọa độ |
| W2 | latitude / longitude swap (lat>90 hoặc lon<-180) | HEAVY | 0.5% | Điền ngược kinh/vĩ độ |
| W3 | warehouse_name có trailing whitespace | LIGHT | 5% | `"Kho HY01 "` — gây mismatch khi JOIN string |
| W4 | is_enabled=True nhưng không có đơn nào trong 90 ngày | LIGHT/ANOMALY | 2% | Ghost warehouse |

### 2.5 `dim_client`

| # | Issue | Loại | Tỷ lệ | Mô tả |
|---|---|---|---|---|
| CL1 | client_type NULL | LIGHT | 1% | Khách chưa phân loại |
| CL2 | Tên shop có ký tự đặc biệt (`<`, `>`, `"`, `'`) | LIGHT | 0.5% | XSS-like chars từ input không sanitize |
| CL3 | province_id trỏ vào province không có district | HEAVY | 0.2% | FK dangling |

### 2.6 `dim_shipper`

| # | Issue | Loại | Tỷ lệ | Mô tả |
|---|---|---|---|---|
| SH1 | truck_plate_number format sai (`ABC-1234` thay vì `29H-37497`) | LIGHT | 2% | Nhập tay sai format |
| SH2 | vehicle_weight_kg = NULL | LIGHT | 4% | Chưa cập nhật xe |
| SH3 | hire_date trong tương lai | HEAVY | 0.3% | Nhập nhầm năm |
| SH4 | is_active=True nhưng hire_date > today | HEAVY | 0.1% | Logic impossible |

---

## 3. Outlier injection

### 3.1 Weight outliers

```python
# Distribution bình thường: lognormal(mean=6.7, sigma=0.9) → median ~800g
# Outlier inject sau khi sample:
WEIGHT_OUTLIER_RULES = [
    # Quá nhẹ — có thể là tài liệu/phong bì
    {"pct": 0.02, "range": (1, 50)},           # 1–50g (2% rows)
    # Quá nặng — hàng freight khai sai đơn vị
    {"pct": 0.005, "range": (200_000, 500_000)}, # 200–500kg in gram (0.5%)
    # Cực đoan — data entry error
    {"pct": 0.001, "range": (1_000_000, 9_999_999)}, # >1 tấn (0.1%)
]
```

### 3.2 COD outliers

```python
COD_OUTLIER_RULES = [
    {"pct": 0.01, "type": "round_billion", "value": 1_000_000_000},  # 1 tỷ — gõ thừa số 0
    {"pct": 0.005, "type": "negative"},                               # Âm — điều chỉnh lỗi
    {"pct": 0.002, "type": "decimal_shifted", "factor": 1000},       # 150,000 → 150,000,000
]
```

### 3.3 Timestamp outliers

```python
TIMESTAMP_OUTLIER_RULES = [
    # Clock skew nhẹ: ±5 phút
    {"pct": 0.03, "type": "skew_minutes", "range": (-5, 5)},
    # Clock skew nặng: ngược chiều thời gian (end < start)
    {"pct": 0.003, "type": "reverse_order"},
    # Timestamp tương lai: tạo đơn ngày mai
    {"pct": 0.002, "type": "future", "days_ahead": (1, 30)},
    # Epoch zero: 1970-01-01 — hệ thống lỗi
    {"pct": 0.001, "type": "epoch_zero"},
]
```

### 3.4 Volume anomaly (để dashboard alert)

```python
VOLUME_ANOMALY = [
    # KTC HY01 tuần 3 tháng 8/2024: volume giảm 60% (sự cố kho)
    {"warehouse_id": 1001, "week": "2024-W32", "multiplier": 0.4},
    # KTC HCM01 tháng 11/2025: tăng 2.5x (mở rộng công suất)
    {"warehouse_id": 1005, "month": "2025-11", "multiplier": 2.5},
    # Shipper ID 0042: COD discrepancy 3 tháng liên tiếp (gian lận)
    {"shipper_id": 42, "months": ["2025-03", "2025-04", "2025-05"],
     "discrepancy_pct": 0.08},
]
```

---

## 4. Sai số có chủ đích (intentional noise)

Khác với dirty data (lỗi hệ thống), sai số có chủ đích mô phỏng **hành vi con người**:

| Sai số | Áp dụng ở đâu | Tỷ lệ | Mô tả |
|---|---|---|---|
| **Làm tròn trọng lượng** | `data_shippingorder_now.weight` | 40% đơn | Nhân viên cân xong làm tròn lên 500g gần nhất |
| **Khai thấp kích thước** | `length`, `width`, `height` | 15% đơn | Để tránh phí converted weight — chiều cao khai 50% thực tế |
| **Cheat thời gian nhập** | `data_inside_history` (session_code) | 12% phiên | Kết thúc phiên sớm hơn thực tế để đạt KPI (từ data `hy01_session_detail` thực) |
| **Ghi nhầm ca làm việc** | `deliver_shift` | 3% | Ca 3 ghi thành Ca 1 |
| **Điền failure_reason mặc định** | `failure_reason` | 25% đơn failed | Ghi `"wrong_address"` cho mọi case dù lý do khác |

---

## 5. Implementation guide cho generators

### Cấu trúc inject function

```python
# src/generators/_dirty.py — module dùng chung

import numpy as np

def inject_nulls(df, column, rate, condition=None):
    """Inject NULL vào column với tỷ lệ rate, tùy chọn chỉ áp dụng khi condition."""
    mask = np.random.random(len(df)) < rate
    if condition is not None:
        mask = mask & condition(df)
    df.loc[mask, column] = None
    return df

def inject_outliers(df, column, rules, rng):
    """Áp dụng danh sách outlier rules lên column."""
    for rule in rules:
        mask = rng.random(len(df)) < rule["pct"]
        if rule["type"] == "range":
            df.loc[mask, column] = rng.integers(*rule["range"], size=mask.sum())
        elif rule["type"] == "negative":
            df.loc[mask, column] = -df.loc[mask, column]
        elif rule["type"] == "reverse_order":
            # swap start/end timestamps
            ...
    return df

def inject_duplicates(df, pk_col, rate):
    """Duplicate một số rows để tạo duplicate PK."""
    n = max(1, int(len(df) * rate))
    dup_rows = df.sample(n=n, replace=False)
    return pd.concat([df, dup_rows], ignore_index=True)

def inject_enum_drift(df, column, old_values, rate):
    """Thay một số giá trị enum mới bằng giá trị cũ / deprecated."""
    mask = np.random.random(len(df)) < rate
    df.loc[mask, column] = np.random.choice(old_values, size=mask.sum())
    return df
```

### Thứ tự inject trong generator

```python
def generate(seed, **kwargs):
    rng = np.random.default_rng(seed)

    # 1. Generate clean base data
    df = _generate_clean(rng, **kwargs)

    # 2. Inject LIGHT issues (không phá load)
    df = inject_nulls(df, "pick_user", rate=0.03)
    df = inject_nulls(df, "deliver_user", rate=0.08)
    df = inject_enum_drift(df, "status", ["DONE", "FINISH"], rate=0.003)

    # 3. Inject HEAVY issues (có chủ đích để test pipeline cleaning)
    # Áp dụng cho data_shippingorder_now
    df = inject_nulls(df, "failure_reason",
                      rate=0.015,
                      condition=lambda d: d["status"] == "failed")
    df = inject_outliers(df, "weight", WEIGHT_OUTLIER_RULES, rng)
    df = inject_duplicates(df, "order_code", rate=0.0005)

    # 4. Inject intentional noise (human behavior)
    df = _inject_weight_rounding(df, rate=0.40)
    df = _inject_dimension_underreport(df, rate=0.15)

    return df
```

### Flag để phân biệt clean vs dirty

Thêm cột `_data_quality` vào raw parquet để dbt staging có thể filter / quarantine:

```python
# Giá trị: "clean" | "light_issue" | "heavy_issue"
# dbt staging: WHERE _data_quality != 'heavy_issue' (hoặc route vào quarantine table)
df["_data_quality"] = "clean"
df.loc[heavy_mask, "_data_quality"] = "heavy_issue"
df.loc[light_mask & ~heavy_mask, "_data_quality"] = "light_issue"
```

---

## 6. Tỷ lệ tổng hợp

| Bảng | Clean | Light issue | Heavy issue | Outlier |
|---|---|---|---|---|
| `data_shippingorder_now` | ~84% | ~11% | ~4% | ~1% |
| `data_inside_history` | ~88% | ~8% | ~3% | ~1% |
| `data_cod` | ~94% | ~4% | ~2% | <1% |
| `data_transportation` | ~90% | ~7% | ~3% | — |
| `data_shipment` | ~87% | ~9% | ~4% | — |
| `dim_warehouse` | ~91% | ~7% | ~2% | — |
| `dim_client` | ~97% | ~2% | ~1% | — |
| `dim_shipper` | ~92% | ~6% | ~2% | — |

**Mục tiêu:** dbt test phải catch được toàn bộ HEAVY issues.
Great Expectations suite validate LIGHT issues và report nhưng không block pipeline.

---

## 7. Danh sách dbt tests cần viết

| Test | Bảng | Catch issue |
|---|---|---|
| `not_null` | `data_shippingorder_now.order_code` | S9 duplicate → unique test |
| `unique` | `data_shippingorder_now.order_code` | S9 |
| `accepted_values` | `data_shippingorder_now.status` | S13 deprecated enum |
| `expression_is_true: end_delivery_time >= created_date` | `data_shippingorder_now` | S4 |
| `expression_is_true: weight >= 0` | `data_shippingorder_now` | S6, S8 |
| `not_null` | `data_shippingorder_now.failure_reason where status='failed'` | S3 |
| `relationships` | `data_shippingorder_now.deliver_warehouse_id → dim_warehouse` | S11 orphan |
| `not_null` | `data_inside_history.action_category` | E2 |
| `not_null` | `data_inside_history.warehouse_id` (warn only) | E5 |
| `expression_is_true: cod_collected <= cod_amount * 1.05` | `data_cod` | C1 |
| `not_null` | `dim_warehouse.latitude, longitude` | W1 |
| `expression_is_true: latitude between -90 and 90` | `dim_warehouse` | W2 |
| `expression_is_true: hire_date <= current_date` | `dim_shipper` | SH3 |
