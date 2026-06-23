# Setup Guide — Logistics Analytics Platform

## Quick Start (3 steps)

```bash
# 1. Clone & generate data (one-time)
git clone <repo>
cd 02-Logistics-Analytics-Platform
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python src/generators/generate_all.py --seed 42   # ~52 min, 59M rows

# 2. Build dbt models (writes warehouse.duckdb)
cd dbt_project
dbt deps && dbt seed && dbt run && dbt test       # ~2 min after data exists

# 3. Start full stack
cd ..\docker
docker compose up -d
```

Services:
- **Airflow**: http://localhost:8080 (admin / admin)
- **Metabase**: http://localhost:3000

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | For generator + dbt |
| Docker Desktop | 4.x | Must be running |
| RAM | 16 GB+ | For 59M-row generation |
| Disk | 15 GB+ | Raw parquet (~2.7 GB) + DuckDB (~5 GB) |

### Python environment

```powershell
cd f:\ChangPH-project\02-Logistics-Analytics-Platform
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Step 1 — Generate synthetic data

```powershell
$env:PYTHONUTF8 = "1"
python src/generators/generate_all.py --seed 42
```

Output: 11 parquet files in `data/raw/` (~2.7 GB total):

| File | Rows |
|---|---|
| data_shippingorder_now.parquet | 5,002,500 |
| data_inside_history.parquet | 41,015,492 |
| data_transportation.parquet | 4,186,545 |
| data_shipment.parquet | 6,149,237 |
| data_cod.parquet | 3,033,008 |
| 6 dim files | 55,005 |

> Same seed = same data. `--seed 42` is reproducible.

---

## Step 2 — Build dbt models (DuckDB warehouse)

```powershell
$env:PYTHONUTF8 = "1"
cd dbt_project
$env:DBT_PROFILES_DIR = (Get-Location).Path

# Install dbt packages (dbt_utils)
..\.venv\Scripts\dbt.exe deps

# Load seed tables (status mapping, SLA thresholds)
..\.venv\Scripts\dbt.exe seed --profiles-dir .

# Build all models: staging -> core -> mart
..\.venv\Scripts\dbt.exe run --profiles-dir .

# Run 89 data quality tests (88 PASS / 1 WARN expected)
..\.venv\Scripts\dbt.exe test --profiles-dir .

# SCD2 snapshot of client tier changes
..\.venv\Scripts\dbt.exe snapshot --profiles-dir .
```

Output: `data/warehouse.duckdb` (~5 GB) with schemas:
- `main_staging` — 11 views (cleaned raw data)
- `main_core` — 11 tables (6 dim + 5 fact, 58M+ rows)
- `main_mart` — 5 tables (pre-aggregated for dashboards)
- `snapshot` — 1 SCD2 snapshot (snap_client_tier)
- `main_seed` — 2 seed tables

> **Note on dbt version**: This project uses dbt-duckdb 1.7.5 + dbt-core 1.7.19
> installed via `pipx` at `C:/Users/ADMIN/pipx/venvs/dbt-core/`.
> The `.venv` in the project has dbt-duckdb 1.8.4 (also works).

---

## Step 3 — Build Docker image + start stack

### One-time: build custom Airflow image

```bash
cd docker
docker build -f Dockerfile.airflow -t logistics-airflow:2.9.3 .
```

> Installs dbt-duckdb 1.7.5 + duckdb 1.1.3 + pyarrow 17.0.0 into the Airflow container.

### Start full stack

```bash
cd docker
docker compose up -d
```

Wait ~60s for all services to become healthy, then check:

```bash
docker compose ps
# Expected:
# logistics-airflow-db-1          healthy
# logistics-airflow-webserver-1   healthy
# logistics-airflow-scheduler-1   up
# logistics-metabase-1            healthy
```

---

## Step 4 — Trigger Airflow DAG

1. Open http://localhost:8080 (admin / admin)
2. Enable DAG `logistics_daily` (toggle in UI)
3. Click "Trigger DAG" to run manually

**Expected result** (~3 minutes total):
```
dbt_seed      success  14s
dbt_run       success  111s
dbt_test      success  17s
dbt_snapshot  success  15s
quality_check success  1s
```

---

## Step 5 — Connect Metabase to DuckDB

1. Open http://localhost:3000
2. Complete initial setup (create admin account)
3. **Add database:**
   - Database type: **DuckDB**
   - Display name: `Logistics Warehouse`
   - File path: `/data/warehouse.duckdb`
   - Click "Save"

4. Metabase will scan the schema. Browse mart tables:
   - `main_mart.mart_daily_kpi` (2,924 rows)
   - `main_mart.mart_hub_performance` (1,992 rows)
   - `main_mart.mart_sla_breakdown` (3,960 rows)
   - `main_mart.mart_failure_reasons` (25 rows)
   - `main_mart.mart_cod_reconciliation` (550 rows)

---

## Docker compose services

| Service | Image | Port | Purpose |
|---|---|---|---|
| airflow-db | postgres:16-alpine | internal | Airflow metadata DB |
| airflow-webserver | logistics-airflow:2.9.3 | 8080 | Airflow UI |
| airflow-scheduler | logistics-airflow:2.9.3 | — | DAG scheduler |
| metabase | metabase/metabase:v0.49.21 | 3000 | BI dashboard |

Volumes:
- `../data` mounted into Airflow containers as `/opt/airflow/data`
- `../dbt_project` mounted as `/opt/airflow/dbt_project`
- `../data/warehouse.duckdb` mounted read-only into Metabase as `/data/warehouse.duckdb`
- `../metabase/plugins/duckdb.metabase-driver.jar` provides DuckDB JDBC driver

---

## Troubleshooting

### dbt Power User extension shows red in VS Code

The extension uses cp1252 encoding. All YAML config files must be pure ASCII.
Fixed in `profiles.yml` and `dbt_project.yml` — no Vietnamese characters in comments.

VS Code settings (`.vscode/settings.json`):
```json
{
  "dbt.dbtPythonPathOverride": "C:/Users/ADMIN/pipx/venvs/dbt-core/Scripts/python.exe",
  "dbt.profilesDirOverride": "${workspaceFolder}/02-Logistics-Analytics-Platform/dbt_project"
}
```

### DAG stuck in queue

The `logistics_daily` DAG is paused by default. Unpause it:
```bash
docker compose exec airflow-scheduler airflow dags unpause logistics_daily
```

### dbt KeyError in container

Add `--no-partial-parse` flag (already set in DAG). If issue persists:
```bash
docker compose exec airflow-scheduler rm -f /opt/airflow/dbt_project/target/partial_parse.msgpack
```

### DuckDB file locked

DuckDB allows multiple read-only connections but only one write connection.
The DAG connects read-only for quality_check; dbt_run connects read-write.
Do not run dbt locally while the Airflow DAG is running.

### Metabase DuckDB driver not loaded

Check logs: `docker compose logs metabase | grep duckdb`
Expected: `Registered driver :duckdb`. If missing, verify the jar exists:
```bash
ls metabase/plugins/duckdb.metabase-driver.jar
# Should be ~58 MB (AlexR2D2/metabase_duckdb_driver v0.2.3)
```
