"""
Load mart CSVs vào PostgreSQL trên Render.
Usage:
    python scripts/load_mart_to_render_pg.py --conn "postgresql://user:pass@host/db"

Lấy connection string từ Render dashboard > PostgreSQL > Connection String (External).
"""

import argparse
import pandas as pd
import sqlalchemy
from pathlib import Path

EXPORT_DIR = Path(__file__).parent / "mart_export"

TABLES = [
    "mart_daily_kpi",
    "mart_hub_performance",
    "mart_sla_breakdown",
    "mart_failure_reasons",
    "mart_cod_reconciliation",
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conn", required=True, help="PostgreSQL connection string")
    args = parser.parse_args()

    engine = sqlalchemy.create_engine(args.conn)

    for table in TABLES:
        csv_path = EXPORT_DIR / f"{table}.csv"
        if not csv_path.exists():
            print(f"  SKIP {table} — CSV not found, run export_mart_to_csv.py first")
            continue

        df = pd.read_csv(csv_path)
        df.to_sql(table, engine, if_exists="replace", index=False)
        print(f"  {table}: {len(df):,} rows loaded")

    print("\nDone — all mart tables loaded to Render PostgreSQL")

if __name__ == "__main__":
    main()
