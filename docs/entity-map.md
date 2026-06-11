# Entity Map — Logistics Analytics Platform
## Mô phỏng mạng lưới vận hành 3PL kiểu GHN

> Entity map này mô tả **domain knowledge** — hiểu business trước khi nhìn vào schema.
> Đây là bước 0.2 (Discovery) của learning-guide: "Data thực tế trông như thế nào?"

---

## 1. Bức tranh tổng thể — Một đơn hàng

```
[CLIENT/SHOP] - tạo đơn -> order_code
  │
  ▼
[ORDER] ── gán/assign ──► SHIPPER (lấy đơn tại nhà CLIENT)
  │
  ▼
BC lấy hàng: PACK nhiều order_code vào 1 kiện
  └──► sinh package_code_1  (chứa order_code này + nhiều order khác cùng tuyến)
  │
  ▼
EXPORT khỏi BC lấy → TRUCK TRIP (trip_code A) → đến KTC
  │
  ▼
KTC: RECEIVE package_code_1
  → UNPACK (rã kiện, package_code_1 kết thúc)
  → PACK lại theo tuyến tiếp theo
  └──► sinh package_code_2  (order_code này + bộ order khác, cùng KTC đích)
  │
  ▼
EXPORT khỏi KTC → TRUCK TRIP (trip_code B) → đến KTC/BC đích
  │
  ▼  (lặp lại nếu qua nhiều KTC — Liên Vùng có thể 3–4 chặng)
BC đích: RECEIVE package_code_2 → UNPACK
  → LASTMILE TRIP: SHIPPER nhận đơn, giao đến CUSTOMER (trip_code riêng, không join truck trip)
  │
  ▼
[CUSTOMER] (nhận hoặc return)

Ghi chú:
  • 1 order_code đi qua N package_code (N = số chặng kho có PACK)
  • 1 package_code chứa M order_code (M = số đơn gom chung tuyến đó)
  • package_code là ID tạm thời tại 1 chặng — không xuyên suốt hành trình
```
---

## 2. Các Entity chính

### ENTITY 1 — ORDER (Đơn hàng)
```
┌─────────────────────────────────────────────────────┐
│  ORDER                                              │
│  Bảng: data_shippingorder_now (~5M rows)            │
├─────────────────────────────────────────────────────┤
│  ID:   order_code (8 ký tự — vd: GYWKQNBY)         │
├─────────────────────────────────────────────────────┤
│  Ai gửi?     shop_id / client_id → CLIENT           │
│  Từ đâu?     from_district_id → DISTRICT            │
│  Đến đâu?    to_district_id → DISTRICT              │
│  Nặng bao?   weight (GRAM) + converted_weight       │
│  Dịch vụ?    service_type_id (2=Nhanh / 5=TK)      │
│  COD?        cod_amount (0 = không COD)             │
│  Tình trạng? status (ready/picking/.../delivered)   │
├─────────────────────────────────────────────────────┤
│  4 vai trò kho:                                     │
│    pick_warehouse_id    → WAREHOUSE (kho lấy)       │
│    deliver_warehouse_id → WAREHOUSE (kho giao đích) │
│    current_warehouse_id → WAREHOUSE (đang ở đâu)    │
│    return_warehouse_id  → WAREHOUSE (kho hoàn)      │
├─────────────────────────────────────────────────────┤
│  Đặc điểm GHN:                                      │
│    • phanloaivung: Nội Tỉnh / Nội Vùng / Liên Vùng │
│    • deliver_shift: Ca 1 / Ca 2 / Ca 3              │
│    • is_sla_breach: giao trễ so cam kết?            │
│    • type_order: deliver (75%) / return (25%)       │
└─────────────────────────────────────────────────────┘

Quan hệ:
  ORDER ──M:N──► PACKAGE (qua data_inside_history — 1 order đi qua nhiều package theo chặng kho, 1 package chứa nhiều order)
  ORDER ──M:N──► WAREHOUSE (1 order đi qua nhiều kho: pick→transit KTC→BC đích; 1 kho xử lý hàng triệu order)
  ORDER ──1:N──► COD RECORD (lịch sử thu COD)
  ORDER ──1:N──► LASTMILE TRIP (mỗi lần giao là 1 attempt)
```

---

### ENTITY 2 — PACKAGE (Kiện hàng)
```
┌─────────────────────────────────────────────────────┐
│  PACKAGE                                            │
│  Bảng: data_inside_history (~40M event rows)        │
│  (package không có bảng dim riêng — chỉ có events) │
├─────────────────────────────────────────────────────┤
│  ID:   package_code (sinh khi PACK tại kho)         │
├─────────────────────────────────────────────────────┤
│  Chứa đơn nào? order_code[] → ORDER (nhiều đơn)    │
│  Ở kho nào?    warehouse_id → WAREHOUSE (event nào  │
│                thì ghi kho đó — 1 package đi qua   │
│                nhiều warehouse theo chặng)           │
│  Ai làm?       user_id → SHIPPER                    │
│  Session?      session_code (ca nhập xe thực tế)    │
├─────────────────────────────────────────────────────┤
│  Vòng đời 1 package tại MỖI kho (1 vòng):          │
│    PACK (kho A)   → đóng kiện, sinh package_code   │
│    EXPORT (kho A) → xuất lên xe → TRUCK TRIP        │
│    RECEIVE (kho B)→ nhập kiện vào kho B             │
│    UNPACK (kho B) → rã kiện, kết thúc package này  │
│    (PACK lại kho B→ sinh package_code MỚI, tiếp tục)│
├─────────────────────────────────────────────────────┤
│  Actions hoàn hàng:                                 │
│    return_receive → nhập hoàn hàng                  │
│    return_export  → xuất hoàn về shop               │
└─────────────────────────────────────────────────────┘

Quan hệ:
  PACKAGE ──M:N──► ORDER (1 package chứa nhiều order; 1 order đi qua nhiều package — bridge: data_inside_history)
  PACKAGE ──M:N──► WAREHOUSE (1 package đi qua nhiều kho theo chặng; 1 kho xử lý nhiều package — mỗi row event = 1 warehouse)
  PACKAGE ──N:1──► TRUCK TRIP (event export đi kèm trip_code)
```

---

### ENTITY 3 — WAREHOUSE (Kho)
```
┌─────────────────────────────────────────────────────┐
│  WAREHOUSE                                          │
│  Bảng: dim_warehouse (~2,000 rows)                  │
├─────────────────────────────────────────────────────┤
│  ID:   warehouse_id                                 │
├─────────────────────────────────────────────────────┤
│  Tên?    warehouse_name                             │
│  Loại?   warehouse_type:                            │
│    KTC   Kho Trung Chuyển — hub liên tỉnh (~8 cái) │
│    BC    Bưu Cục — điểm giao/nhận cuối (~1,992 cái)│
│    VIRTUAL Kho ảo (không có vật lý)                 │
│  Ở đâu?  district_id → DISTRICT → PROVINCE         │
│  Vùng?   region_shortname (HY/HN/HCM/DN/CT)        │
├─────────────────────────────────────────────────────┤
│  8 KTC anchor (hardcode từ GHN thực):               │
│    HY01 Hưng Yên 01  │ HN02/HN03/DX Hà Nội         │
│    HCM01/HCM20       │ CT Cần Thơ │ DN Đà Nẵng     │
└─────────────────────────────────────────────────────┘

Quan hệ:
  WAREHOUSE ──M:N──► ORDER (1 kho xử lý triệu order; 1 order đi qua nhiều kho — 4 vai trò FK trên order + các kho transit thực tế)
  WAREHOUSE ──M:N──► PACKAGE (1 kho xử lý nhiều package; 1 package đi qua nhiều kho theo chặng — bridge: data_inside_history)
  WAREHOUSE ──1:N──► TRUCK TRIP (from/to warehouse)
  WAREHOUSE ──1:N──► LASTMILE TRIP (BC xuất phát)
  WAREHOUSE ──N:1──► DISTRICT → PROVINCE
```

---

### ENTITY 4 — SHIPPER (Nhân viên vận chuyển)
```
┌─────────────────────────────────────────────────────┐
│  SHIPPER                                            │
│  Bảng: dim_shipper (~1,500 rows)                    │
├─────────────────────────────────────────────────────┤
│  ID:   shipper_id (BIGINT) + user_id (VARCHAR GHN)  │
├─────────────────────────────────────────────────────┤
│  Làm ở đâu?  warehouse_id → WAREHOUSE (BC/KTC)     │
│  Năng lực?   performance_tier (A / B / C)           │
│  Xe?         truck_plate_number, vehicle_weight_kg  │
├─────────────────────────────────────────────────────┤
│  GHN dùng 2 field để map shipper:                   │
│    nv_gan   → nhân viên gán đơn (người assign)      │
│    shipper  → nhân viên thực giao (người chạy)      │
│  2 field này thường là cùng 1 người nhưng           │
│  có thể khác nhau khi re-assign                     │
└─────────────────────────────────────────────────────┘

Quan hệ:
  SHIPPER ──1:N──► ORDER (pick_user / deliver_user / return_user)
  SHIPPER ──1:N──► TRUCK TRIP (lái xe tải liên kho)
  SHIPPER ──1:N──► LASTMILE TRIP (giao hàng cuối dặm)
  SHIPPER ──1:N──► COD RECORD (người thu COD)
```

---

### ENTITY 5 — TRUCK TRIP (Chuyến xe tải liên kho)
```
┌─────────────────────────────────────────────────────┐
│  TRUCK TRIP                                         │
│  Bảng: data_transportation (~500k rows)             │
├─────────────────────────────────────────────────────┤
│  ID:   trip_id (ObjectId) + trip_code (VARCHAR)     │
├─────────────────────────────────────────────────────┤
│  Chạy từ?   from_warehouse_id → WAREHOUSE (KTC)     │
│  Chạy đến?  to_warehouse_id → WAREHOUSE (KTC)       │
│  Xe gì?     truck_plate_number, vehicle_weight_kg   │
│  Ai lái?    shipper_id → SHIPPER                    │
│  Loại?      trip_type: linehaul / local / air       │
│  Bao nhiêu? total_number_booking, total_weight (g)  │
│  Chi phí?   cost, gas_numbers                       │
├─────────────────────────────────────────────────────┤
│  Khác LASTMILE:                                     │
│    TRUCK TRIP = xe tải KTC→KTC (linehaul)           │
│    LASTMILE TRIP = xe máy BC→khách hàng             │
└─────────────────────────────────────────────────────┘

Quan hệ:
  TRUCK TRIP ──1:N──► PACKAGE (qua session_code/trip_code trong inside_history)
  TRUCK TRIP ──N:1──► WAREHOUSE (from + to)
  TRUCK TRIP ──N:1──► SHIPPER (tài xế)
```

---

### ENTITY 6 — LASTMILE TRIP (Chuyến giao cuối dặm)
```
┌─────────────────────────────────────────────────────┐
│  LASTMILE TRIP                                      │
│  Bảng: data_shipment (~7.5M rows)                   │
├─────────────────────────────────────────────────────┤
│  ID:   shipment_id                                  │
├─────────────────────────────────────────────────────┤
│  Đơn nào?   order_code → ORDER                      │
│  Chuyến?    trip_code (lastmile namespace riêng —   │
│             KHÔNG join vào data_transportation)      │
│  Ai giao?   shipper_id → SHIPPER                    │
│  Ai gán?    nv_gan (field thực tế của GHN)          │
│  Xuất từ?   warehouse_id → WAREHOUSE (BC)           │
│  Kết quả?   is_succeeded (Boolean)                  │
│  Loại?      type: deliver / return                  │
│  Giao đi?   ship_from_district/province (denorm)    │
│  Đến?       ship_to_district/province (denorm)      │
└─────────────────────────────────────────────────────┘

Quan hệ:
  LASTMILE TRIP ──N:1──► ORDER (1 order có thể giao nhiều lần = attempt)
  LASTMILE TRIP ──N:1──► SHIPPER
  LASTMILE TRIP ──N:1──► WAREHOUSE (BC xuất phát)
```

---

### ENTITY 7 — COD RECORD (Thu hộ tiền mặt)
```
┌─────────────────────────────────────────────────────┐
│  COD RECORD                                         │
│  Bảng: data_cod (~3M rows)                          │
├─────────────────────────────────────────────────────┤
│  ID:   cod_id                                       │
├─────────────────────────────────────────────────────┤
│  Đơn nào?   order_code → ORDER                      │
│  Shop nào?  client_id → CLIENT                      │
│  Ai thu?    shipper_id → SHIPPER                    │
│  Phải thu?  cod_amount (VNĐ)                        │
│  Thực thu?  cod_collected (VNĐ)                     │
│  Chênh?     discrepancy_vnd = collected - amount    │
│  Phí?       delivery_fee + rts_fee + transfer_fee   │
│  Tình trạng? recon_status: matched/pending/disputed  │
│  Đã settled? is_settled (Boolean)                   │
└─────────────────────────────────────────────────────┘

Quan hệ:
  COD RECORD ──N:1──► ORDER
  COD RECORD ──N:1──► CLIENT (để đối soát với shop)
  COD RECORD ──N:1──► SHIPPER (người thu tiền)
```

---

### ENTITY 8 — CLIENT (Đối tác/Shop gửi hàng)
```
┌─────────────────────────────────────────────────────┐
│  CLIENT                                             │
│  Bảng: dim_client (~50,000 rows)                    │
├─────────────────────────────────────────────────────┤
│  ID:   client_id (BIGINT) + shop_id (BIGINT)        │
├─────────────────────────────────────────────────────┤
│  Loại?   client_type:                               │
│    TTS    Thương Tử Số — nhỏ lẻ cá nhân (39%)      │
│    SME    Doanh nghiệp vừa và nhỏ (31%)             │
│    SHOPEE Sàn TMĐT Shopee (29%)                     │
│    LAZADA / TIKI (1%)                               │
│  Hạng?   tier: Bronze/Silver/Gold/Diamond           │
│  Ở đâu?  province_id + district_id                  │
│  B2B?    is_b2b (đơn doanh nghiệp vs cá nhân)      │
├─────────────────────────────────────────────────────┤
│  Pareto: 20% client tạo 60% volume (phân phối GHN) │
└─────────────────────────────────────────────────────┘

Quan hệ:
  CLIENT ──1:N──► ORDER
  CLIENT ──1:N──► COD RECORD (đối soát cuối tháng)
```

---

### ENTITY 9 — PROVINCE / DISTRICT (Địa lý)
```
┌─────────────────────┐     ┌──────────────────────┐
│  PROVINCE (63)      │ 1:N │  DISTRICT (~700)      │
│  Bảng: dim_province │◄────┤  Bảng: dim_district  │
├─────────────────────┤     ├──────────────────────┤
│  province_id        │     │  district_id          │
│  province_name      │     │  district_name        │
│  region (4 miền)    │     │  province_id → PROV   │
│  region_idx (0-3)   │     │  province_name (denorm│
└─────────────────────┘     └──────────────────────┘

4 vùng địa lý:
  Miền Bắc  (region_idx=0) — HN, HP, HY, QN, ...
  Miền Trung (region_idx=1) — ĐN, HUE, QNg, ...
  Tây Nguyên (region_idx=2) — ĐL, GL, KON, ...
  Miền Nam   (region_idx=3) — HCM, ĐT, VT, CT, ...

Quan hệ:
  PROVINCE ──1:N──► DISTRICT
  DISTRICT ──1:N──► WAREHOUSE
  DISTRICT ──1:N──► ORDER (from/to district)
```

---

## 3. Ma trận quan hệ Entity

```
              ORDER  PACKAGE  WAREHOUSE  SHIPPER  TRUCK  LASTMILE  COD  CLIENT  DISTRICT
ORDER           ●     M:N†      M:N†      N:1(×3)   —      1:N      1:N   N:1    N:1(×2)
PACKAGE        M:N†    ●        M:N†      N:1        N:1    —        —     —       —
WAREHOUSE      M:N†   M:N†       ●         —         1:N    1:N      —     —       N:1
SHIPPER       1:N(×3) 1:N        1:N        ●        1:N    1:N      1:N   —       —
TRUCK TRIP      —     1:N        N:1(×2)   N:1        ●      —        —     —       —
LASTMILE TRIP  N:1     —         N:1       N:1        —      ●        —     —       —
COD RECORD     N:1     —         —          N:1       —      —        ●    N:1      —
CLIENT         1:N     —         —           —        —      —       1:N    ●       N:1
DISTRICT        —      —         1:N         —        —      —        —    1:N      ●

† M:N bridge qua data_inside_history
  - mỗi row = 1 action event, gắn package_code + order_code + warehouse_id
  - ORDER↔PACKAGE: 1 order qua nhiều package (mỗi chặng kho); 1 package chứa nhiều order
  - ORDER↔WAREHOUSE: 4 FK cố định trên order + các kho transit qua inside_history
  - PACKAGE↔WAREHOUSE: mỗi event ghi 1 warehouse; 1 package đi qua nhiều warehouse
```

---

## 4. Business flows quan trọng

### Flow 1 — Giao hàng thành công (happy path)
```
CLIENT tạo ORDER
  → ORDER: status = ready_to_pick
  → SHIPPER lấy hàng tại nhà CLIENT
  → ORDER: status = picking → in_transit
  → PACKAGE nhập vào BC (action: receive)
  → PACKAGE đóng vào túi (action: pack)
  → TRUCK TRIP chạy BC → KTC (linehaul)
  → PACKAGE nhập KTC (action: receive)
  → PACKAGE rã túi (action: unpack) → đóng lại theo tuyến
  → TRUCK TRIP chạy KTC → BC đích
  → PACKAGE nhập BC đích (action: receive)
  → LASTMILE TRIP: SHIPPER nhận đơn, giao đến CUSTOMER
  → is_succeeded = TRUE
  → ORDER: status = delivered
  → COD RECORD: status = collected (nếu có COD)
```

### Flow 2 — Giao thất bại → hoàn hàng
```
LASTMILE TRIP → is_succeeded = FALSE
  → failure_reason = wrong_address / not_home / refused
  → ORDER: status = failed (lần 1) → thử lại
  → Sau N lần fail → status = return_to_sender
  → PACKAGE nhập hoàn (action: return_receive)
  → PACKAGE xuất hoàn về CLIENT (action: return_export)
  → COD RECORD: discrepancy (nếu COD đã thu một phần)
```

### Flow 3 — COD reconciliation cuối tháng
```
Cuối tháng:
  Tất cả COD RECORD theo CLIENT → tổng hợp
  cod_collected vs cod_amount → discrepancy_vnd
  Nếu matched → is_settled = TRUE, recon_status = matched
  Nếu disputed → flag để finance team xử lý thủ công
```

---

## 5. Dirty data theo entity

| Entity | Dirty thực tế phổ biến | Loại |
|---|---|---|
| ORDER | weight = 0 (không cân) | HEAVY |
| ORDER | failure_reason = NULL khi status = failed | HEAVY |
| ORDER | deliver_user = NULL khi in_transit | LIGHT |
| ORDER | end_delivery_time < created_date (logic sai) | HEAVY |
| PACKAGE | Duplicate package_code cùng session | HEAVY |
| PACKAGE | action_category = NULL | HEAVY |
| WAREHOUSE | warehouse_name có trailing whitespace | LIGHT |
| WAREHOUSE | latitude/longitude = 0 (không nhập) | LIGHT |
| SHIPPER | truck_plate_number format sai | LIGHT |
| COD | cod_collected > cod_amount × 1.5 (nhập sai) | OUTLIER |
| TRUCK TRIP | total_weight = 0 | HEAVY |
| TRUCK TRIP | trip_date ngoài range 2024–2025 | HEAVY |

---

## 6. Câu hỏi analytics từ entity map này

| Câu hỏi business | Entity liên quan | Mart bảng |
|---|---|---|
| KTC nào đang chậm nhất? | ORDER + WAREHOUSE | mart_hub_performance |
| Shipper nào có tỷ lệ giao thành công cao nhất? | LASTMILE TRIP + SHIPPER | mart_sla_breakdown |
| Route Liên Vùng breach SLA nhiều hơn Nội Tỉnh? | ORDER + PROVINCE | mart_sla_breakdown |
| Client nào có COD tồn đọng nhiều nhất? | COD RECORD + CLIENT | mart_cod_reconciliation |
| Ngày nào trong tuần có volume cao nhất? | ORDER + DIM_DATE | mart_daily_kpi |
| KTC nào có chuyến xe khai thác tốt nhất? | TRUCK TRIP + WAREHOUSE | mart_hub_performance |
| Ca làm việc nào có hiệu suất nhập xe cao nhất? | PACKAGE (session) + WAREHOUSE | mart_hub_performance |
