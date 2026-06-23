# Setup Guide — Logistics Analytics Platform

## Quick Start (3 steps)

```bash
# 1. Clone & generate data (one-time, ~52 min)
git clone https://github.com/ChanC003/logistics-analytics-platform.git
cd logistics-analytics-platform
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python src/generators/generate_all.py --seed 42

# 2. Build dbt models (writes warehouse.duckdb, ~2 min)
cd dbt_project
dbt deps && dbt seed && dbt run && dbt test

# 3. Start full stack (Airflow + Metabase)
cd ..\docker
docker compose up -d
```

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| Metabase | http://localhost:3000 | admin@logistics.local / admin1234! |

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | For generator + dbt |
| Docker Desktop | 4.x | Must be running |
| RAM | 16 GB+ | 59M-row generation peak |
| Disk | 15 GB+ | Raw parquet (~2.7 GB) + DuckDB (~5.1 GB) + Docker images (~3 GB) |

---

## Step 1 — Generate synthetic data

```powershell
$env:PYTHONUTF8 = "1"
python src/generators/generate_all.py --seed 42
```

Output: 11 parquet files in `data/raw/` (~2.7 GB):

| File | Rows |
|---|---|
| data_shippingorder_now.parquet | 5,002,500 |
| data_inside_history.parquet | 41,015,492 |
| data_transportation.parquet | 4,186,545 |
| data_shipment.parquet | 6,149,237 |
| data_cod.parquet | 3,033,008 |
| 6 dim files | 55,005 |
| **Total** | **59,441,787** |

> Same seed = same dataset. `data/raw/` is gitignored — regenerate if missing.

---

## Step 2 — Build dbt models (DuckDB warehouse)

```powershell
$env:PYTHONUTF8 = "1"
cd dbt_project

# Install dbt packages (dbt_utils)
dbt deps --profiles-dir .

# Load seed tables (status mapping, SLA thresholds)
dbt seed --profiles-dir .

# Build all models: staging -> core -> mart (~2 min)
dbt run --profiles-dir .

# Run 89 data quality tests (88 PASS / 1 WARN expected)
dbt test --profiles-dir .

# SCD2 snapshot of client tier
dbt snapshot --profiles-dir .
```

Output: `data/warehouse.duckdb` (~5.1 GB):

| Schema | Contents |
|---|---|
| `main_staging` | 11 views — cleaned + cast + deduped raw data |
| `main_core` | 11 tables — 6 dim + 5 fact (58M+ rows) |
| `main_mart` | 5 tables — pre-aggregated for dashboards |
| `snapshot` | snap_client_tier (SCD2) |
| `main_seed` | seed_status_mapping, seed_sla_threshold |

---

## Step 3 — Build Docker images + start stack

### One-time: build custom images

```bash
cd docker

# Airflow image with dbt-duckdb 1.7.5 + duckdb 1.1.3
docker build -f Dockerfile.airflow -t logistics-airflow:2.9.3 .

# Metabase image on Ubuntu/glibc base (required for DuckDB JNI compatibility)
docker build -f Dockerfile.metabase -t logistics-metabase:0.52.9 .
```

> **Why custom Metabase image?** The official `metabase/metabase` uses Alpine Linux (musl libc).
> The MotherDuck DuckDB JDBC driver requires glibc symbols (`__res_init`, `backtrace`).
> This image uses `eclipse-temurin:21-jre-jammy` (Ubuntu 22.04) as base.

### Download DuckDB driver

```bash
# MotherDuck DuckDB driver v0.3.0 (requires Metabase >= 0.52.9)
curl -L -o metabase/plugins/duckdb.metabase-driver.jar \
  "https://github.com/motherduckdb/metabase_duckdb_driver/releases/download/0.3.0/duckdb.metabase-driver.jar"
```

> Driver is ~73 MB — gitignored, must download before starting Metabase.

### Start full stack

```bash
cd docker
docker compose up -d
```

Wait ~90s for Metabase to start, then check:

```bash
docker compose ps
# Expected:
# logistics-airflow-db-1          healthy
# logistics-airflow-webserver-1   healthy   0.0.0.0:8080->8080/tcp
# logistics-airflow-scheduler-1   up
# logistics-metabase-1            healthy   0.0.0.0:3000->3000/tcp
```

---

## Step 4 — Trigger Airflow DAG

1. Open http://localhost:8080 (admin / admin)
2. Enable DAG `logistics_daily` (toggle in list)
3. Click **Trigger DAG** to run manually

Expected result (~3 min total):

| Task | Status | Duration |
|---|---|---|
| dbt_seed | success | 14s |
| dbt_run | success | 111s |
| dbt_test | success | 17s |
| dbt_snapshot | success | 15s |
| quality_check | success | 1s |

---

## Step 5 — Metabase dashboards

Metabase starts pre-configured with 4 dashboards querying mart tables directly.

Login at http://localhost:3000:
- **Email:** `admin@logistics.local`
- **Password:** `admin1234!`

> **First-time setup:** On a fresh container, Metabase needs initial setup via API
> (creates admin user + connects DuckDB). Run the setup script:
> ```bash
> python docs/metabase_setup.py
> ```
> Or follow manual steps in the Troubleshooting section below.

Navigate to **Collections → Logistics Analytics Platform → Dashboard**:

| Dashboard | Tab | Source table |
|---|---|---|
| Logistics Analytics Platform | KPI Overview | mart_daily_kpi |
| | Hub Performance | mart_hub_performance |
| | SLA Analysis | mart_sla_breakdown + mart_failure_reasons |
| | COD Reconciliation | mart_cod_reconciliation |

---

## Docker compose services

| Service | Image | Port | Purpose |
|---|---|---|---|
| airflow-db | postgres:16-alpine | internal | Airflow metadata DB |
| airflow-init | logistics-airflow:2.9.3 | — | One-shot DB migrate + admin user |
| airflow-webserver | logistics-airflow:2.9.3 | 8080 | Airflow UI |
| airflow-scheduler | logistics-airflow:2.9.3 | — | DAG scheduler (LocalExecutor) |
| metabase | logistics-metabase:0.52.9 | 3000 | Metabase BI (custom Ubuntu image) |

**Volume mounts:**
- `../data` → `/opt/airflow/data` (Airflow reads/writes DuckDB)
- `../dbt_project` → `/opt/airflow/dbt_project` (writable — dbt writes logs)
- `../data/warehouse.duckdb` → `/data/warehouse.duckdb` (Metabase, writable — DuckDB needs write lock)
- `../metabase/plugins` → `/app/plugins` (Metabase plugin scan path)

---

## Troubleshooting

### DAG paused on first start

DAG `logistics_daily` is paused by default. Unpause:
```bash
docker compose exec airflow-scheduler airflow dags unpause logistics_daily
```

### dbt KeyError / partial_parse cache

`--no-partial-parse` flag is already set in the DAG. If issue persists locally:
```bash
rm dbt_project/target/partial_parse.msgpack
```

### DuckDB file locked

Only one write connection allowed at a time.
Do not run `dbt run` locally while the Airflow DAG is running.
`quality_check` uses read-only connection — safe to run concurrently with a reader.

### Metabase DuckDB driver not registered

```bash
docker compose logs metabase | grep -i duckdb
# Expected: "Registered driver :duckdb"
```

If missing, verify driver file exists:
```bash
ls -lh metabase/plugins/duckdb.metabase-driver.jar
# Should be ~73 MB (MotherDuck v0.3.0)
```

If file missing, re-download (see Step 3).

### Metabase: "Cannot open file: Read-only file system"

The `warehouse.duckdb` mount must be **writable** (no `:ro`).
Check `docker/docker-compose.yml` — the mount should be:
```yaml
- ../data/warehouse.duckdb:/data/warehouse.duckdb   # no :ro
```

### Metabase first-time setup (manual)

If the container started fresh with no prior setup:
```bash
# 1. Get setup token
SETUP_TOKEN=$(curl -s http://localhost:3000/api/session/properties | python3 -c "import sys,json; print(json.load(sys.stdin)['setup-token'])")

# 2. Create admin user
curl -s -X POST http://localhost:3000/api/setup \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$SETUP_TOKEN\",\"prefs\":{\"site_name\":\"Logistics Analytics Platform\",\"allow_tracking\":false},\"user\":{\"first_name\":\"Chang\",\"last_name\":\"PH\",\"email\":\"admin@logistics.local\",\"password\":\"admin1234!\",\"site_name\":\"Logistics\"}}"

# 3. Login + add DuckDB database
SESSION=$(curl -s -X POST http://localhost:3000/api/session -H "Content-Type: application/json" -d '{"username":"admin@logistics.local","password":"admin1234!"}')
TOKEN=$(echo $SESSION | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST http://localhost:3000/api/database \
  -H "X-Metabase-Session: $TOKEN" -H "Content-Type: application/json" \
  -d '{"engine":"duckdb","name":"Logistics Warehouse","details":{"database_file":"/data/warehouse.duckdb"}}'
```

Then import dashboard JSON exports from `metabase/dashboards/`.

### dbt Power User VS Code extension shows errors

The extension uses cp1252 encoding. All YAML config files must be pure ASCII.
`profiles.yml` and `dbt_project.yml` already contain no Vietnamese characters.

VS Code settings (`.vscode/settings.json`):
```json
{
  "dbt.dbtPythonPathOverride": "C:/Users/ADMIN/pipx/venvs/dbt-core/Scripts/python.exe",
  "dbt.profilesDirOverride": "${workspaceFolder}/dbt_project"
}
```
