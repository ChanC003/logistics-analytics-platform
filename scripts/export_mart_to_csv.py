"""
Export 5 mart tables từ DuckDB → CSV files để import vào PostgreSQL (Render demo).
Output: scripts/mart_export/*.csv
"""

import duckdb
import pandas as pd
from pathlib import Path

DUCKDB_PATH = Path(__file__).parent.parent / "data" / "warehouse.duckdb"
OUTPUT_DIR  = Path(__file__).parent / "mart_export"

TABLES = [
    "main_mart.mart_daily_kpi",
    "main_mart.mart_hub_performance",
    "main_mart.mart_sla_breakdown",
    "main_mart.mart_failure_reasons",
    "main_mart.mart_cod_reconciliation",
]

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)

    for table in TABLES:
        name = table.split(".")[-1]
        df = con.execute(f"SELECT * FROM {table}").df()
        out = OUTPUT_DIR / f"{name}.csv"
        df.to_csv(out, index=False, encoding="utf-8")
        print(f"  {name}: {len(df):,} rows -> {out.name}")

    con.close()
    print(f"\nDone — {len(TABLES)} files in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
