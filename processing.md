# Processing — 02 Logistics Analytics Platform

**Ngay cap nhat:** 2026-06-23
**Trang thai:** Phase 3 + Phase 4 COMPLETE (Airflow DAG 5/5 success, Metabase live port 3000) — Phase 5 in progress

---

## Cach dung file nay

Moi Phase co 3 block:
- **Ke hoach** -- y tuong ban dau, se tao gi, lam nhu nao
- **Nhat ky thuc te** -- dieu chinh trong qua trinh lam, van de gap, ly do thay doi
- **Tong ket** -- dien sau khi Phase complete, output thuc te, bai hoc

---

## PHASE 0 -- Discovery & Scaffolding `[COMPLETE 2026-06-08]`

**Output:**
- docs/entity-map.md, docs/data-model.md, docs/data-quality-strategy.md, docs/architecture.md, docs/learning-guide.md
- README.md, processing.md

**Quyet dinh chinh:**
- Data: tu sinh 100% Python (Faker + numpy, seed co dinh)
- Power BI -> Metabase self-hosted Docker
- PostgreSQL -> DuckDB file-based
- 3 fact -> 5 fact sat GHN: + data_transportation + data_shipment
- dim_customer -> dim_client + dim_district (dung ten GHN thuc te)
- weight don vi GRAM (GHN thuc te)
- Dirty data strategy: heavy/light/outlier + human noise, flag _data_quality

---

## PHASE 1 -- Data Generation `[COMPLETE 2026-06-08]`

**Output thuc te:** 11 parquet files (snappy) trong data/raw/, ~2.7 GB:

| Bang | Rows | Size |
|---|---|---|
| data_shippingorder_now | 5,002,500 | 537 MB |
| data_inside_history | 41,015,492 | 1,273 MB |
| data_transportation | 4,186,545 | 141 MB |
| data_shipment | 6,149,237 | 232 MB |
| data_cod | 3,033,008 | 96 MB |
| 6 dim files | 55,005 | ~1 MB |
| **Tong** | **59,441,787** | **~2.7 GB** |

Thoi gian generate: 3131s (~52 phut), seed=42.

**Van de da gap:**
- _YEAR_ROWS hardcode 5M -> smoke test sinh 5M thay vi 500. Fix: function doc N_ORDERS runtime
- _assign_dates loop per-order 2578s -> vectorized weight array + single rng.choice
- data_inside_history nhieu bug vectorize -> fix tung cai
- trip_code gan unique per export -> gom theo (from,to,date) + cap 20 packages/trip
- Windows CP1252 -> stdout UTF-8 wrap + PYTHONUTF8=1

---

## PHASE 2 -- DuckDB + dbt `[COMPLETE 2026-06-22]`

**Output thuc te:**
- dbt project logistics (dbt-duckdb 1.7.5 / dbt-core 1.7.19 qua pipx, also works with 1.8.4/.venv)
- warehouse data/warehouse.duckdb (~5.1 GB)

| Layer | Models | Materialize | Schema DuckDB |
|---|---|---|---|
| staging | 11 view (6 dim + 5 fact) | view | main_staging |
| core | 6 dim + 5 fct | table | main_core |
| mart | 5 mart | table | main_mart |
| snapshot | snap_client_tier (SCD2) | snapshot | snapshot |
| seed | seed_status_mapping, seed_sla_threshold | seed | main_seed |

**Row counts:**
- fct_shipping_order: 4,913,037 (deduped, quarantined)
- fct_inside_history: 40,606,614
- fct_transportation: 4,165,657
- fct_shipment: 6,128,573
- fct_cod: 3,000,047
- 6 dim: 55,005
- mart_daily_kpi: 2,924 | mart_hub_performance: 1,992 | mart_sla_breakdown: 3,960
- mart_failure_reasons: 25 | mart_cod_reconciliation: 550

**dbt test:** 88 PASS / 1 WARN / 0 ERROR (89 tests)
- WARN = assert_delivered_no_failure_reason (1,525 dirty light_issue co y)

**Van de chinh:**
- VS Code dbt Power User extension dung cp1252 -> profiles.yml + dbt_project.yml phai pure ASCII
- "Could not find profile 'logistics'" -> global dbt bi conflict (dbt-mysql + snowplow-tracker broken)
  Fix: cai dbt-core 1.7.19 + dbt-duckdb 1.7.5 qua pipx, .vscode/settings.json dung pipx Python
- Quarantine heavy_issue o FACT, dimension giu moi key -> neu drop key dirty o dim, fact bi orphan
- dirty light_issue (delivered+failure_reason) = WARN khong ERROR

---

## PHASE 3 -- Airflow `[COMPLETE 2026-06-23]`

### Ke hoach -> Thuc te

| Ke hoach | Thuc te |
|---|---|
| DAG: generate -> load -> dbt_run -> test -> quality_check | DAG: dbt_seed -> dbt_run -> dbt_test -> dbt_snapshot -> quality_check |
| generate incremental + load_to_duckdb | Bo qua: data da co san tu Phase 1; DAG chi chay transform layer |
| Great Expectations quality gate | Bo qua (phuc tap khong can thiet); thay bang DuckDB Python check don gian |

### Output thuc te

**docker/Dockerfile.airflow:**
```
FROM airflow-custom:2.9.3
RUN /home/airflow/.local/bin/pip install dbt-duckdb==1.7.5 duckdb==1.1.3 pyarrow==17.0.0
```
Image: logistics-airflow:2.9.3

**docker/docker-compose.yml:** Full stack
- airflow-db: postgres:16-alpine (healthy check)
- airflow-init: one-shot DB migrate + admin user
- airflow-webserver: port 8080
- airflow-scheduler: LocalExecutor
- metabase: port 3000 + DuckDB driver + warehouse.duckdb mount

**airflow/dags/logistics_daily.py:**
- 5 tasks: dbt_seed -> dbt_run -> dbt_test -> dbt_snapshot -> quality_check
- DBT_CMD = "DBT_PROFILES_DIR={DBT_DIR} PYTHONUTF8=1 dbt --no-partial-parse"
- quality_check: Python duckdb, 5 mart tables, row count + null key assert

**Test run (2026-06-23):**
- dbt_seed: success 14s
- dbt_run: success 111s (59M rows processed)
- dbt_test: success 17s (88 PASS / 1 WARN)
- dbt_snapshot: success 15s
- quality_check: success 1s
- **Total: 5/5 PASS, ~3 min**

### Van de da gap va fix

| Van de | Fix |
|---|---|
| airflow-init multiline command syntax error | Single-line bash -c "..." |
| dbt OSError: Read-only filesystem (logs) | Remove :ro from dbt_project volume mount |
| DAG stuck in queue after trigger | airflow dags unpause logistics_daily |
| KeyError 'logistics://macros/...' | --no-partial-parse flag + delete partial_parse.msgpack |
| quality_check BinderException warehouse_id not found | mart_cod_reconciliation key = region (not warehouse_id) |
| Python 3.12 LocalExecutor PID mismatch (SIGTERM) | Trang thai scheduler restart giua chung. Trigger lai la chay duoc |

### Bai hoc

- dbt in Docker can --no-partial-parse (manifest cache KeyError voi non-standard project path)
- Airflow LocalExecutor + Python 3.12 co PID mismatch khi scheduler restart giua task. Khong phai bug code -- trigger lai la resolve.
- DuckDB volume mount phai writable (dbt ghi logs/dbt.log, partial_parse.msgpack)
- Quality check don gian (row count + null assert) hieu qua hon Great Expectations cho demo portfolio

---

## PHASE 4 -- Metabase `[COMPLETE 2026-06-23]`

### Output thuc te

**metabase/plugins/duckdb.metabase-driver.jar** (73 MB)
- Source: MotherDuck metabase_duckdb_driver v0.3.0 (DuckDB 1.2.1)
- Registered as :duckdb driver khi Metabase start

**docker/Dockerfile.metabase** -- Ubuntu (glibc) base de DuckDB JNI load duoc:
```dockerfile
FROM eclipse-temurin:21-jre-jammy
# Download metabase.jar v0.52.9 + tao /app/plugins dir
```

**docker-compose.yml metabase service:**
```yaml
build: {context: ., dockerfile: Dockerfile.metabase}
image: logistics-metabase:0.52.9
volumes:
  - ../metabase/plugins:/app/plugins      # /app/plugins = scan path cua Metabase JAR
  - ../data/warehouse.duckdb:/data/warehouse.duckdb  # writable (DuckDB can khong open ro)
```

**Metabase setup (API):**
- Setup token -> POST /api/setup (user + prefs)
- POST /api/session -> session token
- POST /api/database: engine=duckdb, database_file=/data/warehouse.duckdb -> DB ID=2

**Schema sync:** 30 tables (5 mart + 11 core + 11 staging + 3 others)

**4 Dashboards da tao (9 questions):**
- D2: 01 - KPI Overview (3 cards: weekly table + shipment trend + success rate trend)
- D3: 02 - Hub Performance (2 cards: hub table + top 10 bar)
- D4: 03 - SLA Analysis (3 cards: sla table + breach by region + failure pie)
- D5: 04 - COD Reconciliation (1 card: discrepancy table)

JSON exports: metabase/dashboards/ (4 files)

**Verified data returned:**
- mart_daily_kpi: 52 rows (week_start, region, total_orders, success_rate_pct 71.39%)
- mart_hub_performance: 30 rows (top: 2,646 orders, 73.28% success)
- mart_cod_reconciliation: 550 rows (Q4 2025 Mien Nam: 23.23% discrepancy_rate)

### Van de da gap

| Van de | Fix |
|---|---|
| AlexR2D2 v0.2.3 "No method in multimethod connection-details->spec" | Incompatible voi Metabase v0.49.21 -- thu v0.2.6, cung loi |
| DuckDB JNI libstdc++ missing (Alpine) | Alpine khong co glibc -- them apk gcompat, van thieu __res_init etc |
| Nang len Metabase v0.52.9 van Alpine | Van loi glibc symbols |
| Dockerfile.metabase tu Ubuntu (eclipse-temurin:21-jre-jammy) | glibc co san, DuckDB JNI load OK |
| Volume mount /plugins nhung JAR scan /app/plugins | Fix: doi volume -> ../metabase/plugins:/app/plugins |
| DuckDB "Read-only filesystem" khi mount :ro | DuckDB can write lock -- bo :ro |
| /api/dashboard/{id}/cards endpoint not found (v0.52.9) | API doi -> dung PUT /api/dashboard/{id} voi dashcards array |
| Setup API (POST /api/setup) khong include database | Add database rieng qua POST /api/database sau khi setup |

---

## PHASE 5 -- Docker Full Stack + Docs `[IN PROGRESS 2026-06-23]`

### Ke hoach

1. [x] Verify end-to-end stack: all containers up, DAG 5/5 pass, Metabase live
2. [x] Rewrite docs/architecture.md (match thuc te)
3. [x] Rewrite docs/setup.md (3-step quick start, troubleshooting)
4. [x] Update processing.md (file nay)
5. [x] Update README.md (Metabase version, dashboards section, folder structure)
6. [ ] Update data-quality-strategy.md (match thuc te)
7. [ ] Update Portfolio-ChangPH/html/portfolio/js/data.js (project metadata)

### Nguong demo

Recruiter clone repo va lam duoc:
1. python generate_all.py --seed 42 (co san data roi khong can chay lai)
2. cd dbt_project && dbt run && dbt test
3. cd docker && docker compose up -d
4. Mo localhost:8080 (Airflow) + localhost:3000 (Metabase)

---

## Quyet dinh quan trong (timeline)

| Ngay | Quyet dinh | Ly do |
|---|---|---|
| 2026-05-24 | Data: tu sinh 100% bang Python | Control schema, scale, pattern |
| 2026-05-24 | Power BI -> Metabase dashboard | Recruiter mo link xem ngay, khong can Power BI Desktop |
| 2026-05-24 | DuckDB thay vi PostgreSQL | Columnar, file-based, khong can server |
| 2026-06-05 | 3 fact -> 5 fact sat GHN thuc te | Them data_transportation + data_shipment |
| 2026-06-22 | dbt project dung dbt init day du scaffold | User yeu cau co ca snapshot/macros/seed/test |
| 2026-06-22 | Quarantine heavy_issue o FACT, dimension giu moi key | Drop key dirty o dim lam fact orphan |
| 2026-06-22 | dirty light_issue (delivered+failure_reason) = WARN | De analyst thay, pipeline van chay |
| 2026-06-23 | Bo Great Expectations -> DuckDB Python check don gian | GE phuc tap, khong can thiet cho demo portfolio |
| 2026-06-23 | Airflow image from airflow-custom:2.9.3 (Python 3.12) | dbt-duckdb 1.7.5 tuong thich, pip vao /home/airflow/.local |
| 2026-06-23 | Metabase v0.52.9 + MotherDuck driver v0.3.0 | AlexR2D2 v0.2.3/v0.2.6 incompatible voi MB v0.49+. MotherDuck v0.3.0 can MB >= 0.52.9 |
| 2026-06-23 | Custom Dockerfile.metabase (Ubuntu eclipse-temurin:21-jre-jammy) | Alpine khong co glibc --res_init/backtrace symbols ma DuckDB JNI can |
| 2026-06-23 | warehouse.duckdb mount writable (bo :ro) | DuckDB driver can write lock de open file, read-only mount lam connection fail |
| 2026-06-23 | Dung PUT /api/dashboard/{id} voi dashcards array | Metabase v0.52 doi API: /api/dashboard/{id}/cards endpoint da bi xoa |
