"""
logistics_daily DAG -- orchestrate the full logistics analytics pipeline.

Flow: dbt_run -> dbt_test -> dbt_snapshot -> quality_check
Note: Data is pre-generated (data/raw/*.parquet). This DAG runs the
      transform + test + quality layer daily at 06:00 ICT.
"""
import os
import subprocess
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

DBT_DIR = "/opt/airflow/dbt_project"
DATA_DIR = "/opt/airflow/data"
DBT_CMD = f"DBT_PROFILES_DIR={DBT_DIR} PYTHONUTF8=1 dbt --no-partial-parse"

default_args = {
    "owner": "changph",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="logistics_daily",
    description="Logistics analytics pipeline: dbt transform + test + snapshot + quality check",
    schedule_interval="0 6 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["logistics", "dbt", "duckdb"],
    doc_md="""
## logistics_daily

Daily pipeline for the 02-Logistics Analytics Platform.

**Steps:**
1. `dbt_seed` -- load reference seeds (status mapping, SLA thresholds)
2. `dbt_run` -- build staging -> core -> mart (~60s, 59M rows)
3. `dbt_test` -- run 88 data quality tests (PK, FK, enum, business logic)
4. `dbt_snapshot` -- SCD2 snapshot of client tier changes
5. `quality_check` -- Python row-count + null-rate assertions on mart tables

**Data:** pre-generated parquet in `/opt/airflow/data/raw/` (59M rows).
**Warehouse:** DuckDB at `/opt/airflow/data/warehouse.duckdb`.
    """,
) as dag:

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"cd {DBT_DIR} && {DBT_CMD} seed --profiles-dir {DBT_DIR}",
        env={"HOME": "/home/airflow", "PATH": "/home/airflow/.local/bin:/usr/local/bin:/usr/bin:/bin"},
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && {DBT_CMD} run --profiles-dir {DBT_DIR}",
        env={"HOME": "/home/airflow", "PATH": "/home/airflow/.local/bin:/usr/local/bin:/usr/bin:/bin"},
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && {DBT_CMD} test --profiles-dir {DBT_DIR}",
        env={"HOME": "/home/airflow", "PATH": "/home/airflow/.local/bin:/usr/local/bin:/usr/bin:/bin"},
    )

    dbt_snapshot = BashOperator(
        task_id="dbt_snapshot",
        bash_command=f"cd {DBT_DIR} && {DBT_CMD} snapshot --profiles-dir {DBT_DIR}",
        env={"HOME": "/home/airflow", "PATH": "/home/airflow/.local/bin:/usr/local/bin:/usr/bin:/bin"},
    )

    def quality_check(**context):
        """
        Basic quality gate: assert mart tables have expected minimum row counts
        and no null values in key columns.
        """
        import duckdb

        db_path = f"{DATA_DIR}/warehouse.duckdb"
        con = duckdb.connect(db_path, read_only=True)

        checks = [
            ("mart_daily_kpi",          "week_start",    2000),
            ("mart_hub_performance",    "warehouse_id",   100),
            ("mart_sla_breakdown",      "week_start",    1000),
            ("mart_failure_reasons",    "failure_reason",   5),
            ("mart_cod_reconciliation", "region",          10),
        ]

        failures = []
        for table, pk_col, min_rows in checks:
            cnt = con.execute(f"SELECT COUNT(*) FROM main_mart.{table}").fetchone()[0]
            nulls = con.execute(
                f"SELECT COUNT(*) FROM main_mart.{table} WHERE \"{pk_col}\" IS NULL"
            ).fetchone()[0]
            if cnt < min_rows:
                failures.append(f"{table}: only {cnt} rows (expected >= {min_rows})")
            if nulls > 0:
                failures.append(f"{table}.{pk_col}: {nulls} NULL values in key column")

        con.close()

        if failures:
            raise ValueError("Quality check FAILED:\n" + "\n".join(failures))

        print(f"Quality check PASSED -- {len(checks)} tables verified")

    quality_check_task = PythonOperator(
        task_id="quality_check",
        python_callable=quality_check,
    )

    dbt_seed >> dbt_run >> dbt_test >> dbt_snapshot >> quality_check_task
