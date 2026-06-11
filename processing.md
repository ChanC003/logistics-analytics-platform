# Processing — 02 Logistics Analytics Platform

**Ngày cập nhật:** 2026-06-08
**Trạng thái:** Phase 1 complete (59.4M rows generated + verified) — chuẩn bị Phase 2 (DuckDB + dbt)

---

## Cách dùng file này

Mỗi Phase có 3 block:
- **Kế hoạch** — ý tưởng ban đầu, sẽ tạo gì, làm như nào
- **Nhật ký thực tế** — điều chỉnh trong quá trình làm, vấn đề gặp, lý do thay đổi
- **Tổng kết** — điền sau khi Phase complete, output thực tế, bài học

Khi bắt đầu Phase: điền block Kế hoạch.
Trong quá trình làm: append vào Nhật ký.
Khi Phase xong: điền Tổng kết + đánh dấu status = COMPLETE.

---

## PHASE 0 — Discovery & Scaffolding `[COMPLETE 2026-06-08]`

### Kế hoạch ban đầu
**Ý tưởng:** Xây analytics platform cho logistics 3PL mô phỏng GHN — từ data thô đến dashboard.
**Sẽ tạo:** Folder scaffold + README + architecture + data model.
**Cách làm:** Discovery từ OpenMetadata GHN thực tế (21,336 tables) → xác định entity → chọn stack → viết docs.

### Nhật ký thực tế

| Ngày | Thay đổi | Ý tưởng ban đầu | Vấn đề | Chỉnh sửa |
|---|---|---|---|---|
| 2026-05-24 | Data: tự sinh 100% Python | Dùng data thật từ API | Không có quyền truy cập production data | Dùng Faker + numpy, seed cố định để reproducible |
| 2026-05-24 | Thay Power BI → Metabase | Dashboard bằng Power BI Desktop | Recruiter phải cài Power BI để xem | Metabase self-hosted Docker — recruiter mở localhost:3000 là xem ngay |
| 2026-05-24 | DuckDB thay PostgreSQL | PostgreSQL trên Docker | Cần server running, phức tạp khi demo | DuckDB file-based — clone repo là chạy được |
| 2026-06-05 | Thay HTML dashboard → Metabase | Tự viết HTML/JS dashboard | Không phản ánh real BI workflow | Metabase thực tế hơn cho portfolio |
| 2026-06-05 | 3 fact → 5 fact sát GHN | fct_shipments + fct_events + fct_cod | Quá đơn giản, không reflect GHN thực | Thêm data_transportation (truck trips) + data_shipment (lastmile) — đúng tên GHN |
| 2026-06-05 | dim_customer → dim_client + dim_district | dim_customer (30k) | GHN dùng shop/client_id, không có "customer" | dim_client 50k + dim_district 700 rows |
| 2026-06-05 | dim_hub → dim_warehouse | dim_hub 80 rows | GHN không gọi là hub | dim_warehouse 2,000 rows, type KTC/BC |
| 2026-06-05 | Weight unit: kg → gram | weight tính bằng kg | GHN thực tế lưu gram | converted_weight = max(weight, L×W×H÷6) |
| 2026-06-05 | Dirty data strategy | Không có kế hoạch dirty data | Data sạch 100% không realistic | Taxonomy 3 tầng: heavy/light/outlier + human noise, flag `_data_quality` |
| 2026-06-08 | Volume 58M → 56M | 58M tổng | Tính sai tổng | 5M+40M+3M+500k+7.5M = 56M chính xác |
| 2026-06-08 | Staging cho dim có dirty | Dim bỏ qua staging | Dirty data trong dim không được clean | Thêm stg_warehouse / stg_client / stg_shipper |
| 2026-06-08 | Truck trip avg ~20 kiện | avg 200 đơn/chuyến | 200 đơn × 500k trips = 100M > 40M inside_history | avg ~20 kiện/chuyến (package level); 1 kiện chứa nhiều đơn |

### Tổng kết Phase 0

**Output thực tế:**
- `docs/entity-map.md` — 9 entity, business flows, câu hỏi analytics
- `docs/data-model.md` — 5 dim + 5 fact, schema chi tiết, volume 56M+ rows
- `docs/data-quality-strategy.md` — taxonomy 3 tầng, tỷ lệ inject, code template
- `docs/architecture.md` — flow diagram, dbt layout 8 staging + 11 core + 5 mart
- `docs/learning-guide.md` — hướng dẫn thực hành 5 phase
- `README.md`, `processing.md` (file này)

**Bài học:**
- Discovery trước khi thiết kế tiết kiệm nhiều lần làm lại — tên bảng GHN thực tế khác hoàn toàn naming convention thông thường
- Viết entity-map bằng ngôn ngữ business trước khi viết ERD kỹ thuật — dễ review hơn nhiều
- Volume phải tính từ business logic (action/order × chặng) không phải đặt con số tùy ý

---

## PHASE 1 — Data Generation `[COMPLETE 2026-06-08]`

### Kế hoạch ban đầu

**Ý tưởng:** Sinh toàn bộ 56M+ rows synthetic data mô phỏng GHN, reproducible với seed cố định.

**Sẽ tạo:**

| File | Output | Dependency |
|---|---|---|
| `src/generators/config.py` | Constants dùng chung | — |
| `src/generators/dim_province.py` | 63 tỉnh hardcode | — |
| `src/generators/dim_district.py` | ~700 quận/huyện | dim_province |
| `src/generators/dim_date.py` | 730 ngày 2024–2025 | — |
| `src/generators/dim_warehouse.py` | 8 KTC anchor + ~1,992 BC | dim_district |
| `src/generators/dim_client.py` | 50k client, TTS/SME/SHOPEE mix | dim_district |
| `src/generators/dim_shipper.py` | 1.5k shipper, 3 tier A/B/C | dim_warehouse |
| `src/generators/data_shippingorder_now.py` | 5M orders, seasonality + skew | tất cả dim |
| `src/generators/data_inside_history.py` | ~40M package events | data_shippingorder_now, dim_warehouse |
| `src/generators/data_transportation.py` | ~500k truck trips | data_inside_history (export events) |
| `src/generators/data_shipment.py` | ~7.5M lastmile trips | data_shippingorder_now |
| `src/generators/data_cod.py` | ~3M COD records | data_shippingorder_now (đơn có COD) |
| `src/generators/generate_all.py` | Orchestrator CLI | tất cả generator |
| `data/sample/` | 50k rows commit vào git | generate_all |

**Cách làm:**
1. Public API mỗi generator: `generate(seed, **kwargs) -> pd.DataFrame` + `write(df, path) -> None`
2. Output: Parquet snappy, path `data/raw/<table>.parquet`
3. Inject dirty theo `docs/data-quality-strategy.md` — clean base trước, inject sau
4. Flag `_data_quality`: `clean` / `light_issue` / `heavy_issue`
5. Verify: cùng seed → cùng output (diff = empty)

**Rủi ro dự kiến:**
- `data_inside_history` 40M rows có thể slow nếu dùng Python loop — cần vectorized numpy
- Memory: 40M × 10 col × 50 bytes = 20GB uncompressed → cần chunk hoặc write theo tháng
- `generate_all.py` cần đảm bảo thứ tự chạy đúng dependency chain

### Terminal Commands — Phase 1

Tất cả lệnh cần chạy trong Phase 1 (theo thứ tự):

```bash
# 0. Tạo virtualenv + cài dependencies
cd f:\ChangPH-project\02-Logistics-Analytics-Platform
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell / CMD
pip install --timeout 120 -r requirements.txt

# 1. Smoke test nhanh (500 orders, in-memory, không write file)
cd src\generators
$env:PYTHONUTF8=1; python _test_smoke.py   # PowerShell
# set PYTHONUTF8=1 && python _test_smoke.py  # CMD

# 2. Generate full dataset (5M orders, ~56M rows total)
python generate_all.py --seed 42

# 3. Verify reproducibility (chạy lần 2, so sánh output)
python generate_all.py --seed 42
# → diff giữa 2 lần chạy phải empty

# 4. Sample 50k rows đã được generate_all.py tự write vào data/sample/
#    Kiểm tra file tồn tại:
# Windows: dir ..\..\data\sample\
# Git add sample:
# git add data/sample/data_shippingorder_sample.parquet
```

**Lưu ý môi trường:**
- Python 3.11+ required
- RAM ≥ 16GB để load 40M inside_history rows
- Disk ≥ 10GB cho full parquet output
- Working dir khi chạy generator: `src/generators/` (vì path `data/raw/` là relative)

### Nhật ký thực tế

| Ngày | File | Vấn đề gặp | Cách giải quyết |
|---|---|---|---|
| 2026-06-08 | `config.py` | — | Tạo mới, 130+ constants: seeds, multipliers, KTC anchors, dirty rates |
| 2026-06-08 | `_dirty.py` | `inject_nulls` dùng stateless rng không reproducible | Thêm `inject_nulls_seeded()` nhận rng từ caller |
| 2026-06-08 | `dim_province.py` | — | 63 tỉnh hardcode, không random |
| 2026-06-08 | `dim_district.py` | — | ~711 quận/huyện, prefix Quận/Huyện/Thị xã/TP |
| 2026-06-08 | `dim_date.py` | — | 730 ngày 2024–2025, VN holidays, DOW names |
| 2026-06-08 | `dim_warehouse.py` | — | 8 KTC hardcode + 1,992 BC; dirty W1/W3 |
| 2026-06-08 | `dim_client.py` | — | 50k clients, SHOPEE/LAZADA/TIKI → Gold/Diamond |
| 2026-06-08 | `dim_shipper.py` | — | 1,500 shippers, 3 tier A/B/C, plate format dirty |
| 2026-06-08 | `data_shippingorder_now.py` | `kwargs.get("x", pd.read_parquet(...))` eager-eval ngay cả khi đã pass df | Đổi sang `if x is None: x = pd.read_parquet(...)` |
| 2026-06-08 | `data_inside_history.py` | Bản đầu dùng Python for-loop qua 5M orders → quá chậm | Rewrite vectorized: expand bằng `np.repeat`, batch action block |
| 2026-06-08 | `data_transportation.py` | — | Aggregate export events từ inside_history theo trip_code |
| 2026-06-08 | `data_shipment.py` | — | 1.5x attempt/order, 25% retry; prefix "L" ≠ "T" transportation |
| 2026-06-08 | `data_cod.py` | — | 60% orders có COD; thêm adjustment records cho discrepancy |
| 2026-06-08 | `generate_all.py` | — | Orchestrator CLI --seed --sample --only --skip; pass cache qua kwargs |
| 2026-06-08 | Môi trường | Network timeout khi pip install Faker 1.8MB | `pip install --timeout 120` + cài từng batch |
| 2026-06-08 | `.venv` | Chưa tạo môi trường từ đầu | `python -m venv .venv` + cài pandas/numpy/faker/pyarrow |
| 2026-06-08 | `data_shippingorder_now.py` | `_YEAR_ROWS` hardcode 5M rows → smoke test sinh 5M thay vì 500 | Đổi thành function `_get_year_rows()` đọc `N_ORDERS` runtime |
| 2026-06-08 | `data_shippingorder_now.py` | `_assign_dates` loop per-order → 2578s cho 500 đơn | Rewrite vectorized: weight array + single `rng.choice` |
| 2026-06-08 | `data_shippingorder_now.py` | `phanloaivung` trong generator | User: "cái phân loại vùng ý là việc của Analyst sau này". Xoá khỏi tất cả generator |
| 2026-06-08 | `data_inside_history.py` | `order_codes_hops` length 1506 ≠ 4016 (hop-level thay vì row-level) | Fix expand sau khi `hop_of_row` computed |
| 2026-06-08 | `data_inside_history.py` | `searchsorted` IndexError — return_receive/return_export thiếu trong dict | Đổi sang `pd.Series.reindex()` |
| 2026-06-08 | `data_inside_history.py` | `view("U12")` wrong length trong `_rand_codes` | Rewrite dùng `np.char.add` loop 12 cols |
| 2026-06-08 | `data_inside_history.py` | trip_code gán 1 unique per export → avg packages/trip = 1.0 | Group exports theo (from_wh, to_wh, date) với capacity 20, cumsum logic |
| 2026-06-08 | `data_transportation.py` | FutureWarning: set None trên float64 column | Cast sang object trước: `df[col] = df[col].astype(object)` |
| 2026-06-08 | `_dirty.py` | FutureWarning: set None trên bool column | Cast sang object trước khi set |
| 2026-06-08 | Windows encoding | UnicodeEncodeError CP1252 với tiếng Việt | stdout wrap UTF-8 trong smoke test + `$env:PYTHONUTF8=1` |
| 2026-06-08 | Background tasks | Nhiều `python.exe` tiêu tốn 2-3GB RAM mỗi con từ lần chạy cũ | `Stop-Process -Name python -Force` |
| 2026-06-08 | Full generate | Chạy `generate_all.py --seed 42` — 59.4M rows / 3131s (~52 phút) | OK, 11 parquet files vào `data/raw/` |
| 2026-06-08 | Verify `packages/trip` | avg=2.4 (median=1) ở 5M scale — thấp hơn mô tả "~20" | Quyết định GIỮ: long-tail là bản chất thật của mạng 2,000 kho. Route trung tâm gom đủ 20, route BC nhỏ chỉ 1-2/ngày. Không phải bug |
| 2026-06-08 | Verify `order_code` dup | 2,562 trùng (0.05%) — dbt unique test sẽ fail | Quyết định GIỮ: đây là dirty S9 CỐ Ý (~2,500 inject) + ~60 collision tự nhiên (code 8 ký tự). dbt staging sẽ dedup |
| 2026-06-08 | `_verify.py` | Tạo mới — DuckDB verify 9 checks trên parquet (row count, PK, FK, dirty %, namespace) | Giữ lại để re-verify sau mỗi regenerate |

### Tổng kết Phase 1

**Ngày hoàn thành:** 2026-06-08

**Output thực tế:** 11 parquet files (snappy) trong `data/raw/`, tổng ~2.7GB:

| Bảng | Rows | Size |
|---|---|---|
| dim_province | 63 | 0.0 MB |
| dim_district | 711 | 0.0 MB |
| dim_date | 731 | 0.0 MB |
| dim_warehouse | 2,000 | 0.1 MB |
| dim_client | 50,000 | 0.8 MB |
| dim_shipper | 1,500 | 0.1 MB |
| data_shippingorder_now | 5,002,500 | 537 MB |
| data_inside_history | 41,015,492 | 1,273 MB |
| data_transportation | 4,186,545 | 141 MB |
| data_shipment | 6,149,237 | 232 MB |
| data_cod | 3,033,008 | 96 MB |
| **Tổng** | **59,441,787** | **~2.7 GB** |

Sample 50k rows → `data/sample/data_shippingorder_sample.parquet`.
Thời gian generate full: **3131s (~52 phút)**, seed=42.

**Vấn đề đã gặp và fix:**
- `_YEAR_ROWS` hardcode 5M → smoke test sinh 5M thay vì 500. Fix: function đọc `N_ORDERS` runtime
- `_assign_dates` loop per-order 2578s → vectorized weight array + single `rng.choice`
- `phanloaivung` trong generator → xoá hết, để dbt (Analyst) tự derive
- `data_inside_history` nhiều bug vectorize (length mismatch hop vs row, searchsorted IndexError, view U12) → fix từng cái
- trip_code gán unique per export → gom theo (from,to,date) + cap 20 packages/trip
- FutureWarning set None trên typed column (transportation, _dirty) → cast object trước
- Windows CP1252 → stdout UTF-8 wrap + `$env:PYTHONUTF8=1`

**Bài học:**
- Hardcode row count ở module level (`_YEAR_ROWS`) là bẫy — phải đọc config runtime, nếu không smoke test vô dụng
- Vectorize NumPy bắt buộc cho 40M rows — Python loop = chục phút, vectorized = giây
- `kwargs.get("x", expensive())` eager-eval ngay cả khi không cần — dùng `if x is None`
- **Phân biệt bug vs đặc thù dữ liệu:** packages/trip avg 2.4 nhìn "sai" nhưng thực ra là long-tail đúng bản chất mạng 2,000 kho. order_code trùng nhìn "lỗi" nhưng là dirty inject cố ý. Verify phải hiểu intent trước khi gọi FAIL
- Derived field (phanloaivung, region classification) thuộc về transform layer (dbt), KHÔNG sinh ở generator — tách concern rõ ràng

**Số liệu verify (DuckDB, `_verify.py`):**
- Row counts: ✅ khớp kỳ vọng (59.4M tổng)
- PK uniqueness: dim_* PASS; order_code có 2,562 dup (dirty S9 cố ý — chấp nhận)
- packages/trip: avg=2.4, max=20, median=1 (long-tail — chấp nhận)
- `_data_quality`: clean 92.7-98.9%, light 0.8-5.5%, heavy 0.3-1.8% — đúng range thiết kế
- trip_code namespace: ✅ T (transportation) / L (shipment) tách biệt, 0 overlap
- FK integrity: ✅ 0 orphan deliver_warehouse_id
- status: delivered 71.8%, return 9.9%, cancelled 5.0% — đúng; có 0.1% "DONE"/"FINISH" (enum drift dirty cố ý)
- date range: ✅ 2024-01-01 → 2025-12-31
- NULL dirty: inside_history.warehouse_id 5.01%, transportation.vehicle_weight 5.95% (SH2 4% + TR2 2%) — đúng

> **Lưu ý cho Phase 2 (dbt staging):** raw layer CỐ Ý bẩn. Staging phải xử lý: dedup order_code, clean enum drift (DONE/FINISH→delivered), handle NULL warehouse/vehicle_weight, filter `_data_quality='heavy_issue'` nếu cần. Đây là điểm học chính của project.

---

## PHASE 2 — DuckDB + dbt `[CHƯA BẮT ĐẦU]`

### Kế hoạch ban đầu

**Ý tưởng:** Load raw Parquet vào DuckDB, build dbt models 3 tầng (staging → core → mart), đảm bảo dbt test 100% pass.

**Sẽ tạo:**

| File | Output | Ghi chú |
|---|---|---|
| `dbt_project/dbt_project.yml` | Config dbt project | profile: `logistics` |
| `dbt_project/profiles.yml` | Kết nối DuckDB | path: `../data/warehouse.duckdb` |
| `staging/stg_warehouse.sql` | Clean dim_warehouse | TRIM name, fill null lat/lon |
| `staging/stg_client.sql` | Clean dim_client | Null type, special chars |
| `staging/stg_shipper.sql` | Clean dim_shipper | Plate format, future hire_date |
| `staging/stg_shippingorder.sql` | Clean orders | Dedup order_code, cast types |
| `staging/stg_inside_history.sql` | Clean package events | Null action_category |
| `staging/stg_transportation.sql` | Clean truck trips | |
| `staging/stg_shipment.sql` | Clean lastmile | |
| `staging/stg_cod.sql` | Clean COD | |
| `core/dim_*.sql` (6 dim) | Dim tables | |
| `core/fct_*.sql` (5 fct) | Fact tables | |
| `mart/mart_daily_kpi.sql` | Tổng đơn, success rate, SLA, COD | |
| `mart/mart_hub_performance.sql` | Performance từng KTC/BC | |
| `mart/mart_sla_breakdown.sql` | SLA theo region/route/day | |
| `mart/mart_failure_reasons.sql` | Top reason giao thất bại | |
| `mart/mart_cod_reconciliation.sql` | Đối soát COD | |
| `tests/` | pytest cho generator | |

**Cách làm:**
- Staging: view, chỉ rename + cast + basic filter, heavy issues → quarantine
- Core: table, join dim, dedup, business logic
- Mart: table, pre-aggregate, partition theo `week_start`
- dbt test bắt buộc: `not_null` + `unique` cho PK, `relationships` cho FK

### Nhật ký thực tế

*(Điền trong quá trình làm)*

| Ngày | File/Model | Vấn đề gặp | Cách giải quyết |
|---|---|---|---|
| | | | |

### Tổng kết Phase 2

*(Điền sau khi Phase complete)*

**Ngày hoàn thành:**
**Output thực tế:**
**dbt test results:** (số test pass/fail/warn)
**Vấn đề đã gặp và fix:**
**Bài học:**

---

## PHASE 3 — Airflow `[CHƯA BẮT ĐẦU]`

### Kế hoạch ban đầu

**Ý tưởng:** Orchestrate toàn bộ pipeline qua Airflow DAG chạy hàng ngày — generate incremental → load → dbt → quality gate → notify.

**Sẽ tạo:**

| File | Output | Ghi chú |
|---|---|---|
| `airflow/dags/logistics_daily.py` | DAG 5 bước | Schedule 6h sáng hàng ngày |
| `docker/docker-compose.yml` | Airflow + DuckDB volume | |
| `src/quality_check.py` | Great Expectations suite | Quality gate trước publish |

**DAG flow:** generate → load_to_duckdb → dbt_run → dbt_test → quality_check

**Rủi ro dự kiến:**
- Generator hiện tại là batch 2 năm — cần quyết định: chạy lại toàn bộ mỗi ngày hay chỉ append
- DuckDB lock conflict khi Airflow write + Metabase read đồng thời

### Nhật ký thực tế

*(Điền trong quá trình làm)*

| Ngày | Task | Vấn đề gặp | Cách giải quyết |
|---|---|---|---|
| | | | |

### Tổng kết Phase 3

*(Điền sau khi Phase complete)*

**Ngày hoàn thành:**
**Output thực tế:**
**Vấn đề đã gặp và fix:**
**Bài học:**

---

## PHASE 4 — Metabase `[CHƯA BẮT ĐẦU]`

### Kế hoạch ban đầu

**Ý tưởng:** Setup Metabase self-hosted Docker, kết nối DuckDB qua community JDBC driver, build 4 dashboard.

**Sẽ tạo:**

| Item | Chi tiết |
|---|---|
| `docker/docker-compose.yml` update | Thêm Metabase service port 3000, mount DuckDB read-only |
| 4 dashboard | KPI Overview / Hub Performance / SLA Analysis / COD Reconciliation |
| `metabase/dashboards/` | Export JSON để version control |
| `docs/screenshots/` | Capture 4 dashboard cho README |

**Rủi ro dự kiến:**
- `metabase-duckdb-driver.jar` community driver có thể không tương thích Metabase version mới
- Volume mount path trên Windows khác Linux — cần test docker path

### Nhật ký thực tế

*(Điền trong quá trình làm)*

| Ngày | Task | Vấn đề gặp | Cách giải quyết |
|---|---|---|---|
| | | | |

### Tổng kết Phase 4

*(Điền sau khi Phase complete)*

**Ngày hoàn thành:**
**Output thực tế:**
**4 dashboard live:** (URL + screenshot path)
**Vấn đề đã gặp và fix:**
**Bài học:**

---

## PHASE 5 — Docker Full Stack + Demo `[CHƯA BẮT ĐẦU]`

### Kế hoạch ban đầu

**Ý tưởng:** Đóng gói toàn bộ stack thành `docker-compose up` duy nhất — recruiter clone repo và chạy được trong < 5 phút.

**Sẽ tạo:**

| File | Output |
|---|---|
| `docker-compose.yml` (root) | Full stack: Airflow + Metabase + DuckDB volume |
| `docs/setup.md` | 3 bước: clone → generate → docker-compose up |
| Portfolio `data.js` update | Metadata + screenshot link |

### Nhật ký thực tế

*(Điền trong quá trình làm)*

| Ngày | Task | Vấn đề gặp | Cách giải quyết |
|---|---|---|---|
| | | | |

### Tổng kết Phase 5

*(Điền sau khi Phase complete)*

**Ngày hoàn thành:**
**Output thực tế:**
**Demo test:** (clone fresh → up → dashboard trong bao nhiêu phút)
**Bài học:**

---

## Quyết định quan trọng (timeline)

| Ngày | Quyết định | Lý do |
|---|---|---|
| 2026-05-24 | Data: tự sinh 100% bằng Python | Control schema, scale, pattern — không phụ thuộc API |
| 2026-05-24 | Thay Power BI → Metabase dashboard | Recruiter mở link xem ngay, không cần Power BI Desktop |
| 2026-05-24 | DuckDB thay vì PostgreSQL | Columnar, file-based, không cần server — phù hợp 5M+ rows local |
| 2026-05-24 | Volume target: 5M shipments + 20M events (ban đầu) | Đúng tagline "5M+ rows", chứng minh DuckDB shine |
| 2026-06-05 | Thay HTML dashboard → Metabase (self-hosted Docker) | BI tool thực tế hơn cho portfolio — recruiter thấy real BI workflow |
| 2026-06-05 | Cập nhật data-model.md sát GHN thực tế qua OpenMetadata | Column names/types lấy từ `data_shippingorder_now`, `dim_warehouse` — 21,336 tables catalog |
| 2026-06-05 | Đổi `dim_customer` → `dim_client` + thêm `dim_district` | GHN dùng shop/client_id, địa lý phân cấp province→district→ward |
| 2026-06-05 | Đổi `dim_hub` → `dim_warehouse` | GHN không gọi là hub — warehouse_type phân biệt KTC vs BC |
| 2026-06-05 | Trọng lượng đổi sang GRAM | GHN thực tế: `weight` tính bằng gram, `converted_weight = max(weight, L×W×H÷6)` |
| 2026-06-05 | Dirty data strategy: heavy + light + outlier + human noise | Blueprint inject dirty cho mọi generator, flag `_data_quality` để dbt route quarantine |
| 2026-06-05 | Đổi 3 fact → 5 fact sát GHN thực tế | Thêm data_transportation + data_shipment. Volume tăng từ 26M → 56M+ rows |
| 2026-06-08 | Thêm staging cho dim có dirty data | dim_warehouse/client/shipper có dirty — cần clean trước khi vào core |
| 2026-06-08 | Truck trip: avg ~20 kiện/chuyến (không phải 200 đơn) | 200 đơn × 500k trips = 100M > 40M inside_history — không nhất quán |
