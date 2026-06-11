# Setup — Logistics Analytics Platform

## 1. Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Generate synthetic raw data

```powershell
python src/generators/generate_all.py --seed 42 --years 2
```

Kết quả sẽ nằm trong `data/raw/` dưới dạng Parquet.

## 3. Build dbt models

```powershell
cd dbt_project
dbt deps
dbt run
dbt test
```

## 4. Start Airflow + Metabase

```powershell
docker-compose -f docker/docker-compose.yml up -d
```

## 5. Open Metabase

- Trình duyệt: http://localhost:3000
- Kết nối đến DuckDB file `data/warehouse.duckdb`

## 6. Notes

- Metabase dashboard exports nên lưu vào `metabase/dashboards/` để version control.
- Nếu muốn chạy lại toàn bộ pipeline, regenerate data rồi chạy lại `dbt run` trước khi mở Metabase.
# Setup — Logistics Analytics Platform

## 1. Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Generate synthetic raw data

```powershell
python src/generators/generate_all.py --seed 42 --years 2
```

Output sẽ nằm trong `data/raw/`.

## 3. Build dbt models into DuckDB

```powershell
cd dbt_project
dbt run
dbt test
```

## 4. Start Airflow + Metabase

```powershell
docker-compose up -d
```

Sau khi dịch vụ lên, truy cập:

- Airflow UI: `http://localhost:8080`
- Metabase: `http://localhost:3000`

## 5. Metabase setup

- Kết nối Metabase tới DuckDB file `data/warehouse.duckdb`
- Import dashboard JSON exports từ `metabase/dashboards/`
- Xây dựng KPI, hub performance, SLA analysis, COD reconciliation

## 6. Notes

- `data/raw/` giữ raw Parquet; không edit thủ công
- `metabase/dashboards/` lưu export cấu hình dashboard để version control
