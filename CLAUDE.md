# CLAUDE.md — 02 Logistics Analytics Platform

Hướng dẫn riêng cho Claude khi làm việc trong project **02 — Logistics Analytics Platform**. File này **override** các quy ước ở [workspace CLAUDE.md](../CLAUDE.md) khi có xung đột. Còn lại thì kế thừa.

---

## 1. Bối cảnh project

- **Mục tiêu:** Demo end-to-end data platform — synthetic data → DuckDB → dbt → Airflow → Metabase
- **Tagline:** "59M synthetic rows → DuckDB → dbt → Airflow → Metabase dashboards in one docker-compose"
- **Stakeholder:** Recruiter chạy `docker-compose up` — Metabase self-hosted tại `localhost:3000`
- **Trạng thái:** Hoàn thành 5/5 phase — xem [processing.md](processing.md)

## 2. Stack & Convention

| Layer | Tech | Convention |
|---|---|---|
| Generation | Python 3.11+, Faker, numpy, pandas | Seed cố định `--seed 42` để reproducible |
| Storage | DuckDB file `data/warehouse.duckdb` | Không commit file `.duckdb`, gitignore |
| Transform | dbt-duckdb | Model layout: `staging/` → `core/` → `mart/` |
| Orchestration | Apache Airflow (Docker) | DAG: `logistics_daily` |
| Serving | Metabase (self-hosted Docker) | Kết nối DuckDB qua JDBC, `localhost:3000` |
| Test | pytest + dbt test + Great Expectations | Quality gate trước mỗi publish |

## 3. Quy ước SQL (project-specific)

Kế thừa [`sql-style.md`](C:/Users/ADMIN/.claude/rules/sql-style.md), thêm:

- **Engine:** mọi SQL trong project này chạy trên **DuckDB** — declare ở dòng đầu: `-- Engine: DuckDB`
- **Date filter chuẩn:** dùng `created_at::DATE BETWEEN DATE '...' AND DATE '...'` — DuckDB hỗ trợ literal `DATE 'YYYY-MM-DD'`
- **Partition:** model `mart_*` partition theo `week_start` (DATE), KHÔNG dùng string `dt`
- **Naming column:**
  - Đơn vị trong tên: `weight_kg`, `cod_amount_vnd`, `delivery_hours`
  - Boolean: `is_delivered`, `is_sla_breach`, `is_cod`
  - FK: `<dim>_id` → `hub_id`, `customer_id`, `shipper_id`, `province_id`, `date_id`
- **Không SELECT \*** kể cả trong staging — luôn list column tường minh

## 4. Quy ước Python generator

- Mỗi generator là 1 file độc lập trong `src/generators/<dim_xxx | fct_xxx>.py`
- Public API mỗi file:
  ```python
  def generate(seed: int, **kwargs) -> pd.DataFrame: ...
  def write(df: pd.DataFrame, path: Path) -> None: ...  # output .parquet
  ```
- Orchestrator `generate_all.py` import từng module, không monkey-patch
- Output format: **Parquet với snappy compression** — không CSV
- Path output: `data/raw/<table_name>.parquet` (single file < 500MB) hoặc partition theo tháng nếu lớn hơn
- Reproducible: cùng seed → cùng dataset (set `np.random.seed`, `random.seed`, Faker `seed_instance`)

## 5. Quy ước dbt

- Project name: `logistics`
- Profile: `logistics` trỏ tới `../data/warehouse.duckdb`
- Materialization mặc định:
  - `staging/` → `view`
  - `core/` → `table`
  - `mart/` → `table` (partition theo `week_start` nếu > 100k rows)
- Test bắt buộc: `not_null` + `unique` cho PK, `relationships` cho FK
- Không dùng `ref()` lồng quá 3 tầng — refactor ngay nếu vượt
- Macro tự viết để vào `macros/` — naming `<verb>_<noun>.sql` (vd `mask_pii.sql`)

## 6. Quy ước Metabase

- **Deployment:** Custom Docker image `logistics-metabase:0.52.9` (Ubuntu/glibc — `eclipse-temurin:21-jre-jammy`), port `3000`
  - Official Alpine image không dùng được — DuckDB JNI cần glibc (`__res_init`, `backtrace`, `malloc_trim`)
- **DuckDB driver:** MotherDuck driver v0.3.0 (`duckdb.metabase-driver.jar`, ~73MB) — mount vào `/app/plugins/` (KHÔNG phải `/plugins/`)
  - Driver gitignored — download thủ công từ MotherDuck releases trước khi `docker compose up`
- **Volume mount:** `data/warehouse.duckdb` → `/data/warehouse.duckdb` — **KHÔNG** dùng `:ro` (DuckDB driver cần write lock)
- **Dashboard:** 1 dashboard 4 tabs (KPI Overview / Hub Performance / SLA Analysis / COD Reconciliation), tổ chức trong collection 3 tầng (root → Dashboard/Question/Source)
- **Credentials:** `admin@logistics.local` / `admin1234!`
- **Metabase H2 reset mỗi khi restart container** — nếu mất data, chạy lại setup flow (xem docs/setup.md troubleshooting)
- **Metabase không tự sinh data** — phải chạy generator + dbt trước, sau đó Metabase tự query mart tables

## 7. File analysis bắt buộc

Mọi file dữ liệu (parquet, csv, excel) trong project này **bắt buộc** spawn `analyst` sub-agent — không đọc trực tiếp trên main. Tham chiếu [`file-analysis.md`](C:/Users/ADMIN/.claude/rules/file-analysis.md).

Lý do project-specific: dataset target là **5M shipment + 20M event** — đọc trực tiếp sẽ overflow context.

## 8. Tiến trình & memory

- File chính: [`processing.md`](processing.md) — cập nhật sau mỗi phase
- Không tạo file tiến trình trong `~/.claude/projects/` hay memory folder — chỉ dùng `processing.md` cục bộ
- Khi user hỏi "tiến độ", "đang làm tới đâu" → đọc `processing.md` này trước

## 9. Quy ước file lớn (chặn ở `.claude/settings.json`)

| File / Folder | Lý do chặn |
|---|---|
| `data/raw/**.parquet` | Sinh từ generator — không edit thủ công |
| `data/warehouse.duckdb` | Binary file lớn — không Edit/Write |
| `data/mart/**.parquet` | Build từ dbt — không edit thủ công |

Muốn thay đổi → sửa generator hoặc dbt model, regenerate.

## 10. Bước tiếp theo (theo `processing.md`)

1. Tạo `requirements.txt`
2. Implement `src/generators/dim_province.py` (data tĩnh — baseline dễ nhất)
3. Implement các dim còn lại + `data_shippingorder_now.py`
4. Sample 50k rows commit vào `data/sample/`

---

**Tham chiếu:**
- [Workspace CLAUDE.md](../CLAUDE.md) — quy ước chung
- [README.md](README.md) — mục đích + quick start
- [docs/architecture.md](docs/architecture.md) — flow + layer
- [processing.md](processing.md) — tiến độ chi tiết
