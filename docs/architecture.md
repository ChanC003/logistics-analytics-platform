# Architecture — Logistics Analytics Platform

## 1. High-level flow

```
┌─────────────────────┐
│ Synthetic Generator │  Python (Faker, numpy, pandas) — seed=42, reproducible
│  src/generators/    │  59.4M rows | 11 parquet files | ~52 min | ~2.7 GB
└──────────┬──────────┘
           │ .parquet files in data/raw/
           ▼
┌─────────────────────┐
│   data/raw/         │  Bronze layer — raw fact + dim (with injected dirty data)
│   11 parquet files  │  ~2.7 GB, snappy compression
└──────────┬──────────┘
           │ dbt read_parquet via meta.external_location
           ▼
┌─────────────────────┐
│ dbt staging (views) │  Staging layer — clean, cast, dedup, quarantine heavy issues
│  main_staging.*     │  11 views: 6 dim + 5 fact
└──────────┬──────────┘
           │ dbt ref()
           ▼
┌─────────────────────┐
│  dbt core (tables)  │  Core layer — star schema, FK integrity, phanloaivung derived
│  main_core.*        │  6 dim + 5 fct = 58M+ rows
└──────────┬──────────┘
           │ dbt ref()
           ▼
┌─────────────────────┐
│  dbt mart (tables)  │  Mart layer — pre-aggregated for BI, partitioned by week_start
│  main_mart.*        │  5 mart tables, 8,951 total rows
└──────────┬──────────┘
           │ Airflow orchestrates daily
           ▼
┌─────────────────────┐
│  Airflow DAG        │  logistics_daily: dbt_seed → dbt_run → dbt_test → dbt_snapshot
│  localhost:8080     │  → quality_check (5/5 PASS, ~3 min total)
└──────────┬──────────┘
           │ DuckDB file mounted read-only
           ▼
┌─────────────────────┐
│  Metabase Dashboard │  MotherDuck DuckDB driver v0.3.0 (Ubuntu/glibc custom image)
│  localhost:3000     │  4 dashboards: KPI Overview / Hub Performance / SLA Analysis / COD Recon
└─────────────────────┘
```

---

## 2. Layer responsibility

| Layer | Tech | Output | Schema |
|---|---|---|---|
| **Bronze (raw)** | Python generator | 11 `.parquet` files (~2.7 GB) | `data/raw/` |
| **Staging** | dbt (view) | `stg_*` views (cleaned, cast, deduped) | `main_staging` |
| **Core** | dbt (table) | `dim_*` + `fct_*` tables (star schema) | `main_core` |
| **Mart** | dbt (table) | `mart_*` tables (pre-aggregated, weekly) | `main_mart` |
| **Snapshot** | dbt (snapshot) | `snap_client_tier` (SCD2) | `snapshot` |
| **Seed** | dbt (seed) | `seed_status_mapping`, `seed_sla_threshold` | `main_seed` |
| **Orchestration** | Airflow LocalExecutor | DAG `logistics_daily` | — |
| **Serving** | Metabase v0.52.9 | Dashboards on mart tables (4 dashboards, 9 questions) | localhost:3000 |

---

## 3. dbt model layout (actual)

```
dbt_project/
├── models/
│   ├── staging/                           -- 11 models (view)
│   │   ├── stg_warehouse.sql              -- TRIM name, fill null lat/lon, cast float→bool
│   │   ├── stg_client.sql                 -- normalize client_type, null tier default
│   │   ├── stg_shipper.sql                -- clean plate format (keep key for FK integrity)
│   │   ├── stg_shippingorder.sql          -- dedup order_code (ROW_NUMBER), cast types, quarantine heavy
│   │   ├── stg_inside_history.sql         -- null action_category default, cast warehouse FK
│   │   ├── stg_transportation.sql         -- cast float warehouse IDs (NaN→NULL via to_bigint macro)
│   │   ├── stg_shipment.sql               -- cast types, quarantine heavy
│   │   ├── stg_cod.sql                    -- filter adjustment records, cast discrepancy sign
│   │   └── _sources.yml                   -- 11 parquet sources via meta.external_location
│   ├── core/                              -- 11 models (table)
│   │   ├── dim_warehouse.sql              -- 2,000 rows (8 KTC + 1,992 BC)
│   │   ├── dim_province.sql               -- 63 provinces
│   │   ├── dim_district.sql               -- 711 districts
│   │   ├── dim_client.sql                 -- 50,000 clients
│   │   ├── dim_shipper.sql                -- 1,500 shippers
│   │   ├── dim_date.sql                   -- 731 dates (2024–2025)
│   │   ├── fct_shipping_order.sql         -- 4,913,037 rows (deduped, quarantine removed)
│   │   ├── fct_inside_history.sql         -- 40,606,614 rows
│   │   ├── fct_transportation.sql         -- 4,165,657 rows
│   │   ├── fct_shipment.sql               -- 6,128,573 rows
│   │   └── fct_cod.sql                    -- 3,000,047 rows (adjustment records excluded)
│   └── mart/                              -- 5 models (table)
│       ├── mart_daily_kpi.sql             -- 2,924 rows (weekly KPI, 4 metrics per week)
│       ├── mart_hub_performance.sql       -- 1,992 rows (per-warehouse metrics)
│       ├── mart_sla_breakdown.sql         -- 3,960 rows (SLA by region/week)
│       ├── mart_failure_reasons.sql       -- 25 rows (failure reason ranking)
│       └── mart_cod_reconciliation.sql    -- 550 rows (COD by region/year)
├── macros/
│   ├── to_bigint.sql                      -- SAFE_CAST DOUBLE→BIGINT (NaN→NULL)
│   ├── parse_dt.sql                       -- TRY_CAST VARCHAR→DATE
│   ├── normalize_order_status.sql         -- DONE/FINISH→delivered (enum drift cleanup)
│   └── keep_non_quarantine.sql            -- filter WHERE _data_quality != 'heavy_issue'
├── snapshots/
│   └── snap_client_tier.sql               -- SCD2 snapshot of client tier changes
├── seeds/
│   ├── seed_status_mapping.csv            -- status group → display name + is_end flag
│   └── seed_sla_threshold.csv            -- SLA target hours by phanloaivung
├── tests/
│   ├── assert_cod_math.sql               -- COD discrepancy = cod_amount - cod_collected
│   └── assert_delivered_no_failure.sql   -- delivered orders should not have failure_reason (warn)
├── dbt_project.yml                        -- project: logistics, pure ASCII
└── profiles.yml                           -- target: dev, path: ../data/warehouse.duckdb
```

---

## 4. Airflow DAG — `logistics_daily`

**Image:** `logistics-airflow:2.9.3` (FROM airflow-custom:2.9.3 + dbt-duckdb 1.7.5)
**Executor:** LocalExecutor
**Schedule:** `0 6 * * *` (06:00 UTC daily)
**Metadata DB:** PostgreSQL 16-alpine

```
dbt_seed (14s)
    ↓
dbt_run (111s)  -- build staging → core → mart, 58M+ rows
    ↓
dbt_test (17s)  -- 88 PASS / 1 WARN (dirty light_issue expected)
    ↓
dbt_snapshot (15s)  -- SCD2 snap_client_tier
    ↓
quality_check (1s)  -- Python duckdb: 5 mart tables, row count + null key assertions
```

**DAG flags:** `--no-partial-parse` prevents KeyError on manifest cache (Python 3.12 + dbt 1.7 known issue).

**quality_check assertions:**
| Table | Key Column | Min Rows |
|---|---|---|
| mart_daily_kpi | week_start | 2,000 |
| mart_hub_performance | warehouse_id | 100 |
| mart_sla_breakdown | week_start | 1,000 |
| mart_failure_reasons | failure_reason | 5 |
| mart_cod_reconciliation | region | 10 |

---

## 5. Docker compose stack

```yaml
# docker/docker-compose.yml
services:
  airflow-db:        postgres:16-alpine  (metadata DB, healthy check)
  airflow-init:      one-shot DB migrate + admin user create
  airflow-webserver: logistics-airflow:2.9.3  port 8080
  airflow-scheduler: logistics-airflow:2.9.3  LocalExecutor
  metabase:          logistics-metabase:0.52.9  port 3000  (custom Ubuntu image)
                     + /app/plugins/duckdb.metabase-driver.jar (MotherDuck v0.3.0, 73 MB)
                     + /data/warehouse.duckdb (writable mount — DuckDB requires write lock to open)
```

**Volume mounts (Airflow):**
- `../airflow/dags` → `/opt/airflow/dags` (ro)
- `../dbt_project` → `/opt/airflow/dbt_project` (**writable** — dbt writes logs)
- `../data` → `/opt/airflow/data`

---

## 6. Data quality design

**Rule: quarantine at FACT layer, never at dimension.**
Dropping heavy_issue rows from dimension creates orphan facts (broken FK integrity).
Dimensions keep all keys; only attributes are cleaned.

| Stage | Check | Action on fail |
|---|---|---|
| Staging | Filter `_data_quality = 'heavy_issue'` from fact only | Row quarantined, not in core |
| dbt test | 89 tests: not_null/unique (PK), relationships (FK), accepted_values (enum) | Pipeline fails on ERROR, warns on WARN |
| quality_check | Row count + null key assertion on mart tables | Airflow task fails |

**Dirty data injected (by design):**
- order_code duplicates: ~2,562 (dirty S9) — deduped in staging
- status enum drift: DONE/FINISH → normalized to `delivered` in macro
- NULL warehouse FK in inside_history: 5.01% (dirty SH2)
- NULL vehicle_weight: 5.95% (dirty TR2)
- delivered orders with failure_reason: 1,525 (light_issue) → dbt WARN

---

## 7. Performance actuals

| Component | Actual |
|---|---|
| Generate 59M rows | 3,131s (~52 min) |
| dbt full run (in container) | ~111s |
| dbt test (89 tests) | ~17s |
| Metabase init | ~52s |
| Full Airflow DAG | ~3 min |
| DuckDB file size | ~5.1 GB |
| Raw parquet total | ~2.7 GB |

---

## 8. Naming conventions

- **Table prefix:** `stg_` (staging) · `dim_` · `fct_` · `mart_` · `snap_` · `seed_`
- **Column:** snake_case · units in name (`weight_gram`, `cod_amount_vnd`, not yet enforced everywhere)
- **Date column:** `created_at` (timestamp) · `dt` (DATE partition) · `week_start` (mart partition)
- **Boolean:** `is_delivered`, `is_sla_breach`, `is_b2b`, `is_settled`
- **FK:** `<dim>_id` → `warehouse_id`, `client_id`, `shipper_id`, `province_id`, `district_id`, `date_id`
- **Dirty flag:** `_data_quality` → `clean` / `light_issue` / `heavy_issue`
