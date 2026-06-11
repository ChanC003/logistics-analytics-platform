# Data Model — Logistics Analytics Platform

Star schema mô phỏng sát GHN production — column names/types lấy từ OpenMetadata catalog
thực tế (21,336 tables). 5 dim + **5 fact**, tổng ~56M rows ở layer core
(5M order + 40M inside_history + 3M cod + 500k transportation + 7.5M shipment).

---

## 1. ERD

```
                         ┌──────────────┐
                         │  dim_date    │
                         │  (730 rows)  │
                         └──────┬───────┘
                                │
              ┌─────────────────┼──────────────────────┐
              │                 │                      │
   ┌──────────▼──────────┐  ┌───▼──────────────┐  ┌───▼──────────────────┐
   │ data_shippingorder  │  │ data_inside_      │  │   data_cod           │
   │      _now           │  │    history        │  │   (~3M rows)         │
   │    (5M rows)        │  │  (~40M rows)      │  └───┬──────────────────┘
   └──┬──┬──┬──┬──┬──────┘  └──┬──┬────────────┘      │
      │  │  │  │  │            │  │                    │
      │  │  │  │  │     package│  │trip_code           │
      │  │  │  │  │            │  │                    │
      │  │  │  │  └──────────┐ │  └──────────────┐     │
      │  │  │  │             │ │                 │     │
  ┌───▼┐ │ ┌▼────────────┐ ┌▼─▼────────────┐ ┌──▼─────▼───────────┐
  │dim_│ │ │dim_         │ │data_          │ │  data_shipment     │
  │wh  │ │ │client       │ │transportation │ │  (lastmile)        │
  │(2k)│ │ │(50k)        │ │(truck trips)  │ │  (~7.5M rows)      │
  └────┘ │ └─────────────┘ │  (~500k rows) │ └────────────────────┘
         │                 └───────────────┘
    ┌────▼──────────┐
    │ dim_shipper   │
    │   (~1.5k)     │
    └───────────────┘
         │
    ┌────▼──────────┐  ┌────────────────┐
    │ dim_district  ├──► dim_province   │
    │   (~700)      │  │   (63 rows)    │
    └───────────────┘  └────────────────┘
```

**Quan hệ đặc biệt:**
- 1 `order_code` đi qua nhiều `package_code` — mỗi chặng kho tạo package mới khi PACK lại (không phải "tách đơn")
- 1 `package_code` chứa nhiều `order_code` — nhiều đơn gom chung 1 kiện cùng tuyến
- 1 `package_code` → nhiều action rows theo thời gian (receive → pack → export → [receive kho tiếp] → unpack)
- `data_inside_history` là bridge table thực sự cho M:N giữa ORDER, PACKAGE và WAREHOUSE
- `trip_code` trong `data_transportation` (truck trip liên kho) ≠ `trip_code` trong `data_shipment` (lastmile trip) — 2 namespace riêng

---

## 2. Dimensions

### `dim_warehouse` (~2,000 rows)

Nguồn: `ghn-trino.iceberg.dwh.dim_warehouse`

| Column | Type | Mô tả |
|---|---|---|
| warehouse_id | BIGINT PK | |
| warehouse_name | VARCHAR | Vd: `"Kho Trung Chuyển Hưng Yên 01"` |
| warehouse_type | VARCHAR | `KTC` / `BC` / `VIRTUAL` |
| district_id | BIGINT FK | → dim_district |
| province_id | BIGINT FK | → dim_province |
| province_name | VARCHAR | Denorm |
| region_shortname | VARCHAR | `HY` / `HN` / `HCM` / `DN` / `CT` |
| region_fullname | VARCHAR | `Miền Bắc` / `Miền Nam` / `Miền Trung` / `Tây Nguyên` |
| latitude | DOUBLE | |
| longitude | DOUBLE | |
| is_enabled | BOOLEAN | |
| is_virtual | BOOLEAN | |
| created_time | TIMESTAMP | |

**8 KTC anchor (hardcode từ data GHN thực):**

| warehouse_id | warehouse_name | region_shortname |
|---|---|---|
| 1001 | Kho Trung Chuyển Hưng Yên 01 | HY |
| 1002 | Kho Trung Chuyển Hà Nội 02 | HN |
| 1003 | Kho Trung Chuyển Hà Nội 03 | HN |
| 1004 | Kho Trung Chuyển Dương Xá | HN |
| 1005 | Kho Trung Chuyển Hồ Chí Minh 01 | HCM |
| 1006 | Kho Trung Chuyển Hồ Chí Minh 20 | HCM |
| 1007 | Kho Trung Chuyển Cần Thơ | CT |
| 1008 | Kho Trung Chuyển Đà Nẵng 01 | DN |

---

### `dim_province` (63 rows)

Nguồn: `network_provinces.csv` thực tế GHN

| Column | Type | Mô tả |
|---|---|---|
| province_id | BIGINT PK | |
| province_name | VARCHAR | Tên chuẩn hành chính |
| region | VARCHAR | `Miền Bắc` / `Miền Trung` / `Tây Nguyên` / `Miền Nam` |
| region_idx | INTEGER | 0=Bắc · 1=Trung · 2=TN · 3=Nam |

---

### `dim_district` (~700 rows)

Nguồn: pattern từ `data_shippingorder_now.from_district_id`

| Column | Type | Mô tả |
|---|---|---|
| district_id | BIGINT PK | |
| district_name | VARCHAR | |
| province_id | BIGINT FK | → dim_province |
| province_name | VARCHAR | Denorm |

---

### `dim_client` (~50,000 rows)

Nguồn: `data_shippingorder_now.shop_id / client_id`

| Column | Type | Mô tả |
|---|---|---|
| client_id | BIGINT PK | |
| shop_id | BIGINT | Mã cửa hàng |
| client_type | VARCHAR | `TTS` / `SME` / `SHOPEE` / `LAZADA` / `TIKI` |
| province_id | BIGINT FK | |
| district_id | BIGINT FK | |
| is_b2b | BOOLEAN | |
| created_date | DATE | |
| tier | VARCHAR | `Bronze` / `Silver` / `Gold` / `Diamond` |

**Tỷ lệ (từ data thực):** TTS 39% · SME 31% · SHOPEE 29% · khác 1%

---

### `dim_shipper` (~1,500 rows)

Nguồn: `data_shippingorder_now.deliver_user` + `dtm_ops_trip_lastmile_delivery.shipper`

| Column | Type | Mô tả |
|---|---|---|
| shipper_id | BIGINT PK | |
| user_id | VARCHAR | ID trong hệ thống GHN (map `nv_gan` / `shipper` field) |
| warehouse_id | BIGINT FK | BC/KTC phụ trách |
| province_id | BIGINT FK | |
| hire_date | DATE | |
| is_active | BOOLEAN | |
| performance_tier | VARCHAR | `A` / `B` / `C` |
| truck_plate_number | VARCHAR | Biển số xe (vd: `29H-37497`) |
| vehicle_weight_kg | INTEGER | 500/1100/1900/5000/6500/8000/15000 |

---

### `dim_date` (730 rows = 2024–2025)

| Column | Type | Mô tả |
|---|---|---|
| date_id | INTEGER PK | YYYYMMDD |
| date | DATE | |
| year | INTEGER | |
| quarter | INTEGER | |
| month | INTEGER | |
| week_of_year | INTEGER | |
| day_of_week | INTEGER | 1=Mon…7=Sun |
| day_of_week_vn | VARCHAR | `Thu 2`…`Thu 7`, `CN` |
| is_weekend | BOOLEAN | |
| is_holiday_vn | BOOLEAN | |

---

## 3. Facts

### `data_shippingorder_now` (~5M rows)

**Grain:** 1 row = 1 đơn hàng (snapshot trạng thái mới nhất)
**Nguồn thực:** `ghn-trino.dw-ghn.data_internalv2.data_shippingorder_now`
**Partition:** `dt` (DATE)

| Column | Type | Mô tả |
|---|---|---|
| order_code | VARCHAR PK | 8 ký tự uppercase — vd `GYWKQNBY` |
| shop_id | BIGINT FK | → dim_client |
| client_id | BIGINT FK | → dim_client |
| from_name | VARCHAR | Tên người gửi |
| from_phone | VARCHAR | SĐT người gửi (masked: `09xxxxxxx`) |
| from_address | VARCHAR | Địa chỉ người gửi |
| from_ward_code | VARCHAR | Mã phường lấy hàng |
| from_district_id | BIGINT FK | → dim_district |
| to_phone | VARCHAR | SĐT người nhận (masked) |
| to_ward_code | VARCHAR | Mã phường giao hàng |
| to_district_id | BIGINT FK | → dim_district |
| weight | BIGINT | Trọng lượng thực **(gram)** |
| length | BIGINT | Chiều dài (cm) |
| width | BIGINT | Chiều rộng (cm) |
| height | BIGINT | Chiều cao (cm) |
| converted_weight | BIGINT | `max(weight, L×W×H÷6)` — dùng tính phí |
| service_type_id | BIGINT | 2=Nhanh / 5=Tiết kiệm |
| service_id | BIGINT | Mã dịch vụ cụ thể |
| cod_amount | BIGINT | Tiền thu hộ (VNĐ) — 0 nếu không COD |
| cod_collect_date | TIMESTAMP | Ngày/giờ thu COD |
| insurance_value | BIGINT | Giá trị bảo hiểm (VNĐ) |
| pick_station_id | BIGINT FK | → dim_warehouse (`warehouse_type='BC'`) — BC nhận hàng từ shop (station = điểm tiếp nhận); khác `pick_warehouse_id` (xem bên dưới) |
| content | VARCHAR | Nội dung đơn hàng |
| note | VARCHAR | Ghi chú |
| created_source | VARCHAR | Nguồn tạo đơn (`api` / `web` / `mobile`) |
| created_date | TIMESTAMP | Ngày/giờ tạo đơn |
| dt | DATE | **Partition key** |
| date_id | INTEGER FK | → dim_date |
| status | VARCHAR | Trạng thái hiện tại (xem status enum) |
| pick_warehouse_id | BIGINT FK | → dim_warehouse — kho BC xuất phát (thường = pick_station_id; khác nhau khi đơn chuyển BC) |
| deliver_warehouse_id | BIGINT FK | → dim_warehouse (kho giao đích) |
| current_warehouse_id | BIGINT FK | → dim_warehouse (kho đang xử lý) |
| return_warehouse_id | BIGINT FK | → dim_warehouse (kho hoàn trả) |
| deliver_shift | VARCHAR | `Ca 1` / `Ca 2` / `Ca 3` |
| pick_user | BIGINT FK | → dim_shipper (người lấy hàng) |
| deliver_user | BIGINT FK | → dim_shipper (người giao hàng) |
| return_user | BIGINT FK | → dim_shipper (người trả hàng) |
| end_pick_time | TIMESTAMP | Kết thúc lấy hàng |
| first_delivered_time | TIMESTAMP | Lần giao đầu tiên |
| end_delivery_time | TIMESTAMP | Kết thúc giao hàng |
| cod_failed_amount | BIGINT | COD thất bại (VNĐ) |
| cod_failed_collect_date | TIMESTAMP | |
| is_b2b | BOOLEAN | |
| type_order | VARCHAR | `deliver` / `return` |
| type_order_code | VARCHAR | |
| is_sla_breach | BOOLEAN | Tính từ SLA cam kết vs actual |
| failure_reason | VARCHAR | NULL nếu success |
| phanloaivung | VARCHAR | `Nội Tỉnh` / `Nội Vùng` / `Liên Vùng` |
| _data_quality | VARCHAR | `clean` / `light_issue` / `heavy_issue` |

**Status enum (từ `data_order_full_status` thực tế):**

| group_code | group_name | is_end |
|---|---|---|
| `ready_to_pick` | Chờ lấy hàng | false |
| `picking` | Đang lấy hàng | false |
| `in_transit` | Đang vận chuyển | false |
| `delivering` | Đang giao | false |
| `delivered` | Đã giao | **true** |
| `failed` | Giao thất bại | false |
| `return_to_sender` | Hoàn hàng | **true** |
| `cancelled` | Đã hủy | **true** |

---

### `data_inside_history` (~40M rows)

**Grain:** 1 row = 1 hành động (action) trên 1 package tại 1 kho
**Nguồn thực:** `ghn-trino.iceberg.clean.inside_package_history`
**Partition:** `dt` (VARCHAR `YYYY-MM-DD`)

> **Quan hệ đặc biệt:** `data_inside_history` là bridge table M:N giữa ORDER ↔ PACKAGE ↔ WAREHOUSE.
> - 1 `order_code` đi qua nhiều `package_code` vì mỗi lần PACK tại kho mới sẽ sinh `package_code` mới.
> - 1 `package_code` chứa nhiều `order_code` vì nhiều đơn được gom vào 1 kiện cùng tuyến.
> - `package_code` là ID của kiện tại 1 chặng kho cụ thể — không phải ID xuyên suốt hành trình đơn hàng.

| Column | Type | Mô tả |
|---|---|---|
| dt | VARCHAR | **Partition key** — `YYYY-MM-DD` |
| action_time | TIMESTAMP | Ngày/giờ thực hiện hành động |
| action_category | VARCHAR | Nhóm hành động (xem enum bên dưới) |
| action_name | VARCHAR | Tên hành động chi tiết |
| package_code | VARCHAR | ID kiện tại 1 chặng kho — sinh khi PACK, hết hiệu lực sau UNPACK tại kho tiếp; 1 order đi qua nhiều package_code, 1 package_code chứa nhiều order_code |
| order_code | VARCHAR FK | → data_shippingorder_now |
| warehouse_id | BIGINT FK | → dim_warehouse (kho đang xử lý) |
| from_warehouse_id | BIGINT FK | → dim_warehouse (kho xuất phát) |
| to_warehouse_id | BIGINT FK | → dim_warehouse (kho đích) |
| trip_code | VARCHAR FK | → data_transportation.trip_code |
| trip_partner | VARCHAR | Tên đối tác vận chuyển |
| stop_code | VARCHAR | Mã điểm dừng |
| session_code | VARCHAR | Mã phiên làm việc (map với ca nhập xe thực tế) |
| user_id | VARCHAR FK | → dim_shipper.user_id |
| user_name | VARCHAR | Tên người thực hiện |
| _data_quality | VARCHAR | `clean` / `light_issue` / `heavy_issue` |

**action_category enum (từ data `hy_xuat_3dot_may2026.csv` thực tế):**

| action_category | action_name ví dụ | Mô tả |
|---|---|---|
| `receive` | `receive_package` | Nhập kiện vào kho |
| `pack` | `pack_to_bag` | Đóng kiện vào túi/bao |
| `unpack` | `unpack_bag` | Rã túi/bao ra |
| `export` | `export_to_truck` | Xuất kiện lên xe |
| `return_receive` | `receive_return` | Nhập hoàn hàng |
| `return_export` | `export_return` | Xuất hoàn về shop |

---

### `data_cod` (~3M rows)

**Grain:** 1 row = 1 bản ghi COD của 1 đơn hàng (thường 1:1 với order có COD; có thể có adjustment record nếu thu lại)
**Nguồn thực:** `ghn-bigquery.dw-ghn.data_internalV2.data_CODSchedule` +
`ghn-bigquery.dw-ghn.data_internalV2.data_so_history_cod_amount`
**Partition:** `dt` (DATE)

| Column | Type | Mô tả |
|---|---|---|
| cod_id | BIGINT PK | |
| order_code | VARCHAR FK | → data_shippingorder_now |
| client_id | BIGINT FK | → dim_client |
| shipper_id | BIGINT FK | → dim_shipper (người thu COD) |
| dt | DATE | **Partition key** |
| recon_month | DATE | Tháng đối soát (ngày 1 của tháng) |
| cod_amount | BIGINT | Tiền COD phải thu (VNĐ) |
| cod_collected | BIGINT | Tiền COD thực thu (VNĐ) |
| discrepancy_vnd | BIGINT | `cod_collected - cod_amount` |
| from_region | VARCHAR | Miền gửi — denorm từ `dim_province.region`, không phải FK |
| to_region | VARCHAR | Miền nhận — denorm từ `dim_province.region`, không phải FK |
| delivery_fee | BIGINT | Phí giao (VNĐ) |
| rts_fee | BIGINT | Phí hoàn hàng / RTS (VNĐ) |
| total_shipping_fee | BIGINT | `delivery_fee + rts_fee` |
| transfer_fee | BIGINT | Phí chuyển tiền COD cho shop |
| status | VARCHAR | `pending` / `collected` / `transferred` / `disputed` |
| recon_status | VARCHAR | `matched` / `pending` / `disputed` |
| is_settled | BOOLEAN | |
| collect_date | TIMESTAMP | Ngày/giờ thu COD thực tế |
| settled_at | TIMESTAMP | NULL nếu chưa settled |
| _data_quality | VARCHAR | `clean` / `light_issue` / `heavy_issue` |

---

### `data_transportation` (~500k rows)

**Grain:** 1 row = 1 chuyến xe tải (truck trip) liên kho
**Nguồn thực:** `ghn-trino.dw-ghn.data_freight.data_truck_trip_cost` +
`ghn-bigquery.dw-ghn.dataprofiling.Pfl_logistic_truck_trip`
**Partition:** `trip_date` (DATE)

> **Phạm vi:** Vận chuyển **giữa các KTC/BC** — xe tải trung chuyển (linehaul),
> **không phải** giao hàng last-mile đến khách.

| Column | Type | Mô tả |
|---|---|---|
| trip_id | VARCHAR PK | `_id` từ MongoDB (ObjectId format) |
| trip_code | VARCHAR UNIQUE | Mã chuyến — vd `E26052331WZUDIF` — FK target từ `data_inside_history` |
| trip_reference_code | VARCHAR | Mã tham chiếu nội bộ |
| trip_date | DATE | **Partition key** |
| date_id | INTEGER FK | → dim_date (YYYYMMDD) |
| trip_date_ts | TIMESTAMP | Timestamp chính xác khởi hành |
| hub_id | BIGINT FK | → dim_warehouse (KTC xuất phát — `hub` field) |
| from_warehouse_id | BIGINT FK | → dim_warehouse |
| to_warehouse_id | BIGINT FK | → dim_warehouse |
| truck_plate_number | VARCHAR | Biển số xe — vd `29H-37497` |
| driver | VARCHAR | Tên tài xế (denorm từ GHN source — dùng để display) |
| shipper_id | BIGINT FK | → dim_shipper (FK chính thức để JOIN; `driver` chỉ để hiển thị) |
| trip_type | VARCHAR | `linehaul` / `local` / `air` |
| status | VARCHAR | `pending` / `in_transit` / `arrived` / `completed` / `cancelled` |
| is_block | BOOLEAN | Chuyến bị block |
| is_full | BOOLEAN | Xe đầy |
| total_weight | BIGINT | Tổng khối lượng hàng trên xe (gram) |
| total_number_booking | INTEGER | Tổng số đơn/kiện trên chuyến |
| current_cubic | DOUBLE | Thể tích hiện tại (m³) |
| cost | DECIMAL | Chi phí chuyến (VNĐ) |
| gas_numbers | VARCHAR | Số lít nhiên liệu |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| _data_quality | VARCHAR | `clean` / `light_issue` / `heavy_issue` |

---

### `data_shipment` (~7.5M rows)

**Grain:** 1 row = 1 đơn hàng trong 1 chuyến giao last-mile
**Nguồn thực:** `ghn-bigquery.ghn-reporting.ops.dtm_ops_trip_lastmile_delivery` +
`ghn-trino.ghn-platforms.freight_logistic.fact_trip_shipment_allocation`
**Partition:** `load_date` (DATE)

> **Phạm vi:** Giao hàng **từ BC đến tay khách** — shipper chạy xe máy last-mile.
> Khác hoàn toàn `data_transportation` (xe tải liên kho).

| Column | Type | Mô tả |
|---|---|---|
| shipment_id | BIGINT PK | |
| order_code | VARCHAR FK | → data_shippingorder_now |
| trip_code | VARCHAR FK | Mã chuyến lastmile — namespace riêng, **KHÔNG join** vào `data_transportation.trip_code` (truck trip liên kho) |
| trip_reference_code | VARCHAR | Mã tham chiếu chuyến |
| load_date | DATE | **Partition key** (ngày giao) |
| date_id | INTEGER FK | → dim_date (YYYYMMDD) |
| shipper_id | BIGINT FK | → dim_shipper (người giao last-mile) |
| nv_gan | VARCHAR | Mã nhân viên gán đơn (`nv_gan` field thực tế) |
| warehouse_id | BIGINT FK | → dim_warehouse (BC xuất phát) |
| type | VARCHAR | `deliver` / `return` |
| shipment_status | VARCHAR | Trạng thái vận chuyển (freight_logistic schema) |
| is_succeeded | BOOLEAN | Giao thành công hay không |
| trip_status | VARCHAR | `pending` / `assigned` / `in_progress` / `completed` |
| allocation_factor | DOUBLE | Hệ số phân bổ chuyến |
| ship_from_district | VARCHAR | Quận/huyện lấy hàng (denorm) |
| ship_from_province | VARCHAR | Tỉnh lấy hàng (denorm) |
| ship_to_district | VARCHAR | Quận/huyện giao hàng (denorm) |
| ship_to_province | VARCHAR | Tỉnh giao hàng (denorm) |
| service_type | VARCHAR | Loại dịch vụ |
| created_time | TIMESTAMP | |
| updated_time | TIMESTAMP | |
| _data_quality | VARCHAR | `clean` / `light_issue` / `heavy_issue` |

---

## 4. Realistic patterns inject

### 4a. Business patterns (clean data)

| Pattern | Value / Implementation |
|---|---|
| **Trọng lượng** | GRAM — lognormal, median ~800g, range 100–30,000g |
| **Converted weight** | `max(weight, L×W×H÷6)` |
| **Seasonality** | Tháng 11–12: ×1.6 · Tháng 2 (Tết): ×0.5 |
| **Day-of-week** | Mon–Thu: 1.0× · Fri: 1.15× · Sat: 0.9× · Sun: 0.4× |
| **Ca làm việc** | Ca 1 (6–14h) · Ca 2 (14–22h) · Ca 3 (22–6h) |
| **Geographic skew** | HCM 35% + HN 25% + 5 tỉnh lớn 20% + còn lại 20% |
| **Phân loại vùng** | Nội Tỉnh ~30% · Nội Vùng ~40% · Liên Vùng ~30% |
| **Service mix** | service_type_id=2 (Nhanh) 60% · service_type_id=5 (Tiết kiệm) 40% |
| **Client type** | TTS 39% · SME 31% · SHOPEE 29% · khác 1% |
| **type_order** | deliver 75% · return 25% |
| **COD rate** | ~60% đơn có cod_amount > 0 |
| **Package/order** | 1 order đi qua avg 2 package_code (1 BC lấy + 1 KTC trung chuyển); Liên Vùng có thể 3–4 chặng |
| **action_category mix** | receive ~25% · export ~25% · pack ~25% · unpack ~25% (cân đối theo vòng đời) |
| **Truck trip volume** | 5–50 kiện/chuyến (package level), avg ~20; 1 kiện chứa nhiều đơn — 1 chuyến thực tế chở 50–500 đơn hàng |
| **Lastmile trip volume** | 20–60 đơn/chuyến shipper/ngày; avg 1.5 attempt/order |
| **SLA breach** | Nội Tỉnh 3–5% · Nội Vùng 7–10% · Liên Vùng 10–15% |
| **Failure reasons** | wrong_address 40% · not_home 30% · refused 15% · damaged 8% · other 7% |
| **KTC anomaly** | 2–3 KTC breach rate 15–25% — để Metabase alert |
| **Shipper performance** | Tier A: SLA 95% · Tier B: 85% · Tier C: 70% |
| **COD discrepancy** | 0.5% order-tháng có discrepancy ≠ 0 |
| **Pareto client** | 20% client tạo 60% volume |

### 4b. Dirty data inject

Chi tiết đầy đủ: [docs/data-quality-strategy.md](data-quality-strategy.md)

**Tỷ lệ tổng hợp:**

| Bảng | Clean | Light issue | Heavy issue | Outlier |
|---|---|---|---|---|
| `data_shippingorder_now` | ~84% | ~11% | ~4% | ~1% |
| `data_inside_history` | ~88% | ~8% | ~3% | ~1% |
| `data_cod` | ~94% | ~4% | ~2% | <1% |
| `data_transportation` | ~90% | ~7% | ~3% | — |
| `data_shipment` | ~87% | ~9% | ~4% | — |

---

## 5. Volume targets

| Bảng | 2024 | 2025 | Total |
|---|---|---|---|
| `data_shippingorder_now` | 2.0M | 3.0M | **5M** |
| `data_inside_history` | 16M | 24M | **40M** (avg ~8 actions/order — mỗi kho 4 actions × avg 2 kho/đơn) |
| `data_cod` | 1.2M | 1.8M | **3M** (~60% đơn có COD) |
| `data_transportation` | 200k | 300k | **500k** |
| `data_shipment` | 3.0M | 4.5M | **7.5M** (avg ~1.5 attempt/order — ~25% đơn fail retry, còn lại 1 lần) |

Distribution theo tháng (áp dụng cả 2 năm):

```
Jan  ███████       6.5%
Feb  ███            3.5%   ← Tết
Mar  ████████      7.5%
Apr  ████████      7.5%
May  █████████     8.0%
Jun  █████████     8.0%
Jul  █████████     8.0%
Aug  █████████     8.5%
Sep  ██████████    9.0%
Oct  ██████████    9.5%
Nov  █████████████ 12.0%  ← 11.11 + Black Friday
Dec  █████████████ 12.0%  ← Cuối năm
```

---

## 6. Nguồn tham chiếu (GHN OpenMetadata)

| Bảng sinh | Mô phỏng từ bảng GHN thực | Engine |
|---|---|---|
| `data_shippingorder_now` | `ghn-trino.dw-ghn.data_internalv2.data_shippingorder_now` | Trino |
| `data_inside_history` | `ghn-trino.iceberg.clean.inside_package_history` | Trino |
| `data_cod` | `data_CODSchedule` + `data_so_history_cod_amount` | BigQuery |
| `data_transportation` | `data_truck_trip_cost` + `Pfl_logistic_truck_trip` | Trino + BQ |
| `data_shipment` | `dtm_ops_trip_lastmile_delivery` + `fact_trip_shipment_allocation` | BQ + Trino |
| `dim_warehouse` | `ghn-trino.iceberg.dwh.dim_warehouse` | Trino |
| `dim_province` | `network_provinces.csv` (DA workspace) | — |
| `dim_district` | pattern từ `from_district_id` / `to_district_id` | Trino |
| `dim_client` | `data_shippingorder_now.shop_id / client_id` | Trino |
| `dim_shipper` | `deliver_user` + `dtm_ops_trip_lastmile_delivery.shipper` | Trino + BQ |
