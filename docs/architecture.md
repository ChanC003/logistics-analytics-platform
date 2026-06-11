# Architecture — Logistics Analytics Platform

## 1. High-level flow

```
┌─────────────────────┐
│ Synthetic Generator │  Python (Faker, numpy, pandas)
│  src/generators/    │  Seed-controlled, reproducible
└──────────┬──────────┘
           │ writes .parquet
           ▼
┌─────────────────────┐
│   data/raw/         │  Bronze layer — raw fact + dim
└──────────┬──────────┘
           │ COPY INTO
           ▼
┌─────────────────────┐
│      DuckDB         │  warehouse.duckdb (file-based, columnar)
│   warehouse.duckdb  │
└──────────┬──────────┘
           │ dbt-duckdb
           ▼
┌─────────────────────┐
│   dbt Models        │  staging → core → mart
│  dbt_project/       │
└──────────┬──────────┘
           │ orchestrated by
           ▼
┌─────────────────────┐
│  Airflow Orchestrate│  Daily DAG: generate → load → dbt run → test
│   airflow/dags/     │
└──────────┬──────────┘
           │ connects to
           ▼
┌─────────────────────┐
│  Metabase Dashboard │  Self-hosted Docker, DuckDB native connector
│  localhost:3000     │  KPI + hub performance + SLA + COD
└─────────────────────┘
```

## 2. Layer responsibility

| Layer | Tech | Output | Quy ước |
|---|---|---|---|
| **Bronze (raw)** | Python generator | `.parquet` theo bảng | 1 file = 1 table, partition theo tháng nếu > 1M row |
| **Silver (staging)** | dbt | `stg_*` view | Cleanup: rename, cast type, basic filter — không join |
| **Gold (core)** | dbt | `fct_*`, `dim_*` table | Star schema, có PK/FK test |
| **Mart (business)** | dbt | `mart_*` table | Pre-aggregated cho Metabase, partition theo tuần |
| **Serving** | Metabase | Dashboard, Question, Chart | Kết nối trực tiếp DuckDB qua JDBC connector |

## 3. dbt model layout

```
dbt_project/models/
├── staging/
│   ├── stg_warehouse.sql              ← dim_warehouse (clean: TRIM name, fill null lat/lon)
│   ├── stg_client.sql                 ← dim_client (clean: null type, special chars)
│   ├── stg_shipper.sql                ← dim_shipper (clean: plate format, future hire_date)
│   ├── stg_shippingorder.sql          ← data_shippingorder_now
│   ├── stg_inside_history.sql         ← data_inside_history (package events)
│   ├── stg_transportation.sql         ← data_transportation (truck trips)
│   ├── stg_shipment.sql               ← data_shipment (lastmile)
│   └── stg_cod.sql                    ← data_cod
│   (dim_province, dim_district, dim_date: không cần staging — data tĩnh/hardcode, không có dirty)
├── core/
│   ├── dim_warehouse.sql
│   ├── dim_province.sql
│   ├── dim_district.sql
│   ├── dim_client.sql
│   ├── dim_shipper.sql
│   ├── dim_date.sql
│   ├── fct_shippingorder.sql          ← từ data_shippingorder_now
│   ├── fct_inside_history.sql         ← từ data_inside_history
│   ├── fct_transportation.sql         ← từ data_transportation
│   ├── fct_shipment.sql               ← từ data_shipment (lastmile)
│   └── fct_cod.sql                    ← từ data_cod
└── mart/
    ├── mart_daily_kpi.sql              ← Tổng đơn, success rate, SLA, COD
    ├── mart_hub_performance.sql        ← Performance từng hub
    ├── mart_sla_breakdown.sql          ← Phân tích SLA theo region/route
    ├── mart_failure_reasons.sql        ← Top reason fail
    └── mart_cod_reconciliation.sql     ← Đối soát COD
```

## 4. Airflow DAG

**DAG: `logistics_daily`**

```
generate_data (1x/ngày, sinh incremental rows)
    ↓
load_to_duckdb (COPY raw .parquet vào DuckDB)
    ↓
dbt_run (build staging → core → mart)
    ↓
dbt_test (data contract: not_null, unique, accepted_values, relationships)
    ↓
quality_check (Great Expectations gate)
    ↓
notify_slack (success/fail)
```

Metabase tự kết nối DuckDB — không cần bước export JSON. Retry: 2 lần, backoff exponential. SLA alert: 30 phút.

## 5. Quality gates

| Stage | Check | Action nếu fail |
|---|---|---|
| Post-generate | Row count > threshold | Block, alert |
| Post-load | DuckDB count == file count | Block, retry |
| Post-dbt-run | dbt test pass | Quarantine mart, alert |
| Pre-publish | Great Expectations: KPI in range | Hold publish, alert |

## 6. Metabase setup

**Self-hosted via Docker** — chạy song song với Airflow trong `docker-compose.yml`.

| Item | Value |
|---|---|
| Image | `metabase/metabase:latest` |
| Port | `3000` |
| DuckDB connector | `metabase-duckdb-driver` (community JDBC driver) |
| DB path (in container) | `/data/warehouse.duckdb` (volume mount từ host) |
| Dashboard folders | KPI Overview / Hub Performance / SLA Analysis / COD Reconciliation |

**Dashboard plan:**

| Dashboard | Key metrics |
|---|---|
| KPI Overview | Total shipments, success rate, SLA breach %, avg delivery time, total COD |
| Hub Performance | Throughput / hub, top 10 busiest hub, regional breakdown |
| SLA Analysis | Breach rate by region / route type / day-of-week, trend 4 tuần |
| COD Reconciliation | Collection rate, pending COD by shipper, daily reconciliation status |

**Export for version control:** Dashboard JSON export lưu vào `metabase/dashboards/` — reproducible khi setup môi trường mới.

## 7. Naming conventions

- **Table:** snake_case, prefix theo layer (`stg_`, `dim_`, `fct_`, `mart_`)
- **Column:** snake_case, đơn vị trong tên (`weight_kg`, `cod_amount_vnd`, `delivery_hours`)
- **Date:** `created_at` (timestamp), `dt` (date string `YYYY-MM-DD` cho partition)
- **Boolean:** `is_*` (vd `is_delivered`, `is_sla_breach`)
- **Foreign key:** `<dim>_id` (vd `hub_id`, `customer_id`)

## 8. Performance budget

| Component | Target |
|---|---|
| Generate 5M shipments | < 5 phút |
| Load raw → DuckDB | < 30 giây |
| dbt full refresh | < 2 phút |
| Metabase dashboard load | < 2 giây (query mart tables trực tiếp) |
| Metabase container | ~512MB RAM |
