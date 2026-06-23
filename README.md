# 02 — Logistics Analytics Platform

End-to-end analytics platform simulating a Vietnamese 3PL network — 59M synthetic rows from generation through DuckDB, dbt, Airflow orchestration, and Metabase dashboards. Full stack runs locally with one `docker compose up`.

---

## Status

| Phase | Component | Status |
|---|---|---|
| 1 | Data generation (59M rows, 11 parquet) | COMPLETE |
| 2 | DuckDB + dbt (88 PASS / 1 WARN / 0 ERROR) | COMPLETE |
| 3 | Airflow DAG (5/5 tasks success, ~3 min) | COMPLETE |
| 4 | Metabase (DuckDB driver, port 3000) | COMPLETE |
| 5 | Docs + demo-ready | IN PROGRESS |

---

## Quick Start

```bash
# 1. Generate synthetic data (one-time, ~52 min)
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python src/generators/generate_all.py --seed 42

# 2. Build DuckDB warehouse
cd dbt_project
dbt deps && dbt seed && dbt run && dbt test

# 3. Start Airflow + Metabase
cd ..\docker
docker compose up -d
```

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| Metabase | http://localhost:3000 | setup on first visit |

Full guide: [docs/setup.md](docs/setup.md)

---

## Tech Stack

| Layer | Tool | Detail |
|---|---|---|
| Generation | Python + Faker + numpy | Seed-controlled, 59.4M rows reproducible |
| Storage | DuckDB (file-based) | `data/warehouse.duckdb` (~5.1 GB) |
| Transform | dbt-duckdb 1.7.5 | staging → core → mart, 11+11+5 models |
| Orchestration | Apache Airflow 2.9.3 | LocalExecutor, daily DAG `logistics_daily` |
| Serving | Metabase v0.52.9 | MotherDuck DuckDB driver v0.3.0 (Ubuntu-based custom image, glibc) |
| Container | Docker Compose | 5 services: postgres + 2x airflow + airflow-init + metabase |

---

## Dataset

Synthetic data modeled on real GHN logistics operations (Vietnamese 3PL):

| Table | Rows | Description |
|---|---|---|
| data_shippingorder_now | 5,002,500 | Shipment orders (snapshot of current state) |
| data_inside_history | 41,015,492 | Package action events at each warehouse |
| data_transportation | 4,186,545 | Truck trips between warehouses (linehaul) |
| data_shipment | 6,149,237 | Last-mile delivery trips to customers |
| data_cod | 3,033,008 | COD collection and reconciliation records |
| 6 dimension tables | 55,005 | Warehouse, province, district, client, shipper, date |
| **Total** | **59,441,787** | |

**Realistic patterns injected:** seasonality (Nov–Dec peak 1.6x, Feb Tet 0.5x), day-of-week variance,
geographic skew (HCM 35% + HN 25%), SLA breach 3–15% by route type, failure reason distribution,
dirty data at 1–16% with 3-tier severity (`_data_quality` flag).

---

## Data Pipeline

```
Synthetic Generator (Python, seed=42)
    ↓  11 parquet files, ~2.7 GB
data/raw/
    ↓  dbt read_parquet (meta.external_location)
dbt staging  — 11 views: clean, cast, dedup, quarantine heavy_issue
    ↓
dbt core     — 11 tables: star schema, 58M+ rows (6 dim + 5 fct)
    ↓
dbt mart     — 5 tables: pre-aggregated weekly (8,951 total rows)
    ↓  snapshot SCD2: snap_client_tier
dbt snapshot + 89 tests (88 PASS / 1 WARN)
    ↓
Airflow DAG logistics_daily
    dbt_seed (14s) → dbt_run (111s) → dbt_test (17s) → dbt_snapshot (15s) → quality_check (1s)
    ↓
Metabase — queries main_mart.* directly via DuckDB JDBC
```

---

## dbt Models

```
models/
├── staging/ (11 views)   — clean raw data, handle dirty patterns
├── core/    (11 tables)  — star schema: 6 dim + 5 fct
└── mart/    (5 tables)   — pre-aggregated for BI
    ├── mart_daily_kpi          (2,924 rows) — weekly KPI
    ├── mart_hub_performance    (1,992 rows) — per-warehouse metrics
    ├── mart_sla_breakdown      (3,960 rows) — SLA by region/week
    ├── mart_failure_reasons    (25 rows)    — failure reason ranking
    └── mart_cod_reconciliation (550 rows)   — COD by region/year

macros/    — to_bigint, parse_dt, normalize_order_status, keep_non_quarantine
snapshots/ — snap_client_tier (SCD2)
seeds/     — seed_status_mapping, seed_sla_threshold
tests/     — assert_cod_math, assert_delivered_no_failure (warn)
```

---

## Airflow DAG

**DAG:** `logistics_daily` — runs dbt transform + test + quality gate daily at 06:00 UTC

```
dbt_seed → dbt_run → dbt_test → dbt_snapshot → quality_check
  14s        111s       17s         15s              1s
                                             Total: ~3 min
```

Image `logistics-airflow:2.9.3` = `airflow-custom:2.9.3` + dbt-duckdb 1.7.5 + duckdb 1.1.3

---

## Metabase Dashboards

4 dashboards querying mart tables directly via DuckDB JDBC:

| Dashboard | Questions | Source Table |
|---|---|---|
| 01 - KPI Overview | Weekly KPI table + Shipment trend + Success rate trend | `mart_daily_kpi` |
| 02 - Hub Performance | Hub table + Top 10 throughput bar | `mart_hub_performance` |
| 03 - SLA Analysis | SLA table + Breach by region + Failure distribution | `mart_sla_breakdown`, `mart_failure_reasons` |
| 04 - COD Reconciliation | Discrepancy by region/quarter | `mart_cod_reconciliation` |

Dashboard JSON exports: `metabase/dashboards/`

---

## Why DuckDB?

- **Zero-setup demo:** warehouse is a single `.duckdb` file — no server required
- **Performance:** vectorized columnar execution handles 5M+ row analytics in seconds
- **Modern stack:** dbt-duckdb is a highlighted combo in the community for local analytics
- **Portfolio differentiation:** [01-Banking-Pipeline](../01-Banking-Pipeline/) uses Postgres + Snowflake;
  this project demonstrates "local lakehouse" pattern — complementary, not redundant

---

## Folder Structure

```
02-Logistics-Analytics-Platform/
├── README.md            -- this file (actual stack + status)
├── processing.md        -- phase-by-phase journal with decisions + issues
├── requirements.txt     -- Python deps for generator
├── docs/
│   ├── architecture.md  -- detailed flow, layer responsibility, actuals
│   ├── data-model.md    -- schema, ERD, volume targets
│   ├── setup.md         -- step-by-step setup + troubleshooting
│   └── screenshots/     -- Airflow + Metabase screenshots
├── src/generators/      -- 12 Python files: 6 dim + 5 fact + generate_all.py
├── dbt_project/         -- dbt-duckdb project (profiles.yml pure ASCII)
│   ├── models/          -- staging/ core/ mart/
│   ├── macros/          -- to_bigint, parse_dt, normalize_order_status
│   ├── snapshots/       -- snap_client_tier (SCD2)
│   ├── seeds/           -- status_mapping, sla_threshold
│   └── tests/           -- singular business logic tests
├── airflow/dags/        -- logistics_daily.py
├── metabase/plugins/    -- duckdb.metabase-driver.jar (MotherDuck v0.3.0, 73 MB, DuckDB 1.2.1)
├── metabase/dashboards/ -- 4 dashboard JSON exports (01-kpi, 02-hub, 03-sla, 04-cod)
├── docker/
│   ├── docker-compose.yml   -- full stack (postgres + 2x airflow + metabase)
│   ├── Dockerfile.airflow   -- logistics-airflow:2.9.3 with dbt-duckdb
│   └── Dockerfile.metabase  -- logistics-metabase:0.52.9 (Ubuntu/glibc + MotherDuck DuckDB driver)
└── data/
    ├── raw/             -- 11 parquet files (gitignored, regenerate with seed=42)
    ├── sample/          -- 50k row sample (committed)
    └── warehouse.duckdb -- DuckDB file (~5.1 GB, gitignored)
```

---

## Known Issues / Design Decisions

- **dbt Power User VS Code extension**: requires pure ASCII in YAML files (cp1252 encoding).
  `profiles.yml` and `dbt_project.yml` have no Vietnamese characters.

- **DuckDB single-writer**: only one process can write at a time.
  Airflow DAG runs dbt sequentially; quality_check uses read-only connection.
  Do not run `dbt run` locally while the Airflow DAG is running.

- **1 WARN in dbt test**: `assert_delivered_no_failure_reason` — 1,525 delivered orders with
  a failure_reason field. This is **intentional dirty data** (light_issue) injected in the generator.
  The test uses `severity: warn` to surface it without failing the pipeline.

- **data_transportation volume**: 4.19M rows vs 500k target — long-tail distribution.
  Most trips have 1–2 packages (small BC routes); only hub-to-hub routes reach 20 packages/trip.
  This reflects real logistics network behavior, not a generator bug.
