"""Verify Phase 1 output — chạy DuckDB query trên parquet, in báo cáo PASS/FAIL."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import duckdb

RAW = "../../data/raw"
con = duckdb.connect()

def q(sql):
    return con.sql(sql).fetchall()

def one(sql):
    return con.sql(sql).fetchone()[0]

print("="*70)
print("  PHASE 1 DATA VERIFICATION")
print("="*70)

# 1. Row counts
print("\n[1] ROW COUNTS")
tables = ["dim_province", "dim_district", "dim_date", "dim_warehouse",
          "dim_client", "dim_shipper", "data_shippingorder_now",
          "data_inside_history", "data_transportation", "data_shipment", "data_cod"]
for t in tables:
    n = one(f"SELECT COUNT(*) FROM '{RAW}/{t}.parquet'")
    print(f"    {t:<32} {n:>14,}")

# 2. PK uniqueness
print("\n[2] PK UNIQUENESS")
checks = [
    ("data_shippingorder_now", "order_code"),
    ("dim_warehouse", "warehouse_id"),
    ("dim_client", "client_id"),
    ("dim_shipper", "shipper_id"),
]
for t, c in checks:
    total = one(f"SELECT COUNT(*) FROM '{RAW}/{t}.parquet'")
    distinct = one(f"SELECT COUNT(DISTINCT {c}) FROM '{RAW}/{t}.parquet'")
    verdict = "PASS" if total == distinct else "FAIL"
    print(f"    {verdict}  {t}.{c}: total={total:,} distinct={distinct:,}")

# 3. packages/trip (the fixed bug)
print("\n[3] PACKAGES/TRIP (transportation) — bug da fix, ky vong avg ~15-20")
stats = one(f"""SELECT AVG(n_packages), MIN(n_packages), MAX(n_packages),
               COUNT(*) FILTER (WHERE n_packages=1)*100.0/COUNT(*)
               FROM '{RAW}/data_transportation.parquet'""")
avg_pkg = con.sql(f"""SELECT AVG(n_packages) avg_p, MIN(n_packages) min_p,
                MAX(n_packages) max_p,
                COUNT(*) FILTER (WHERE n_packages=1)*100.0/COUNT(*) pct1
                FROM '{RAW}/data_transportation.parquet'""").fetchone()
verdict = "PASS" if avg_pkg[0] >= 5 else "FAIL (still ~1!)"
print(f"    {verdict}  avg={avg_pkg[0]:.1f}  min={avg_pkg[1]}  max={avg_pkg[2]}  pct_single={avg_pkg[3]:.1f}%")

# 4. _data_quality distribution
print("\n[4] _DATA_QUALITY DISTRIBUTION (ky vong clean~90% light~7-8% heavy~2-3%)")
for t in ["data_shippingorder_now", "data_inside_history",
          "data_transportation", "data_shipment", "data_cod"]:
    rows = q(f"""SELECT _data_quality, COUNT(*)*100.0/SUM(COUNT(*)) OVER () pct
                 FROM '{RAW}/{t}.parquet' GROUP BY 1 ORDER BY 2 DESC""")
    dist = ", ".join(f"{r[0]}={r[1]:.1f}%" for r in rows)
    print(f"    {t:<28} {dist}")

# 5. trip_code namespace
print("\n[5] TRIP_CODE NAMESPACE (transportation=T, shipment=L, overlap=0)")
t_bad = one(f"""SELECT COUNT(*) FROM '{RAW}/data_transportation.parquet'
               WHERE trip_code NOT LIKE 'T%'""")
l_bad = one(f"""SELECT COUNT(*) FROM '{RAW}/data_shipment.parquet'
               WHERE trip_code NOT LIKE 'L%'""")
print(f"    {'PASS' if t_bad==0 else 'FAIL'}  transportation non-T prefix: {t_bad:,}")
print(f"    {'PASS' if l_bad==0 else 'FAIL'}  shipment non-L prefix: {l_bad:,}")

# 6. FK integrity — orders.deliver_warehouse_id in dim_warehouse
print("\n[6] FK INTEGRITY (orders.deliver_warehouse_id -> dim_warehouse)")
orphan = one(f"""SELECT COUNT(*) FROM '{RAW}/data_shippingorder_now.parquet' o
    WHERE o.deliver_warehouse_id IS NOT NULL
    AND o.deliver_warehouse_id NOT IN (SELECT warehouse_id FROM '{RAW}/dim_warehouse.parquet')""")
print(f"    {'PASS' if orphan==0 else 'FAIL'}  orphan deliver_warehouse_id (non-null, no match): {orphan:,}")

# 7. status distribution
print("\n[7] ORDER STATUS DISTRIBUTION (delivered~72% return~10% cancelled~5%)")
rows = q(f"""SELECT status, COUNT(*)*100.0/SUM(COUNT(*)) OVER () pct
             FROM '{RAW}/data_shippingorder_now.parquet' GROUP BY 1 ORDER BY 2 DESC""")
for r in rows:
    print(f"    {r[0]:<20} {r[1]:>6.1f}%")

# 8. Date range
print("\n[8] DATE RANGE (orders.created_date, must be 2024-01-01..2025-12-31)")
dr = con.sql(f"""SELECT MIN(created_date), MAX(created_date)
                FROM '{RAW}/data_shippingorder_now.parquet'""").fetchone()
ok = str(dr[0])[:4] in ("2024","2025") and str(dr[1])[:4] in ("2024","2025")
print(f"    {'PASS' if ok else 'FAIL'}  min={dr[0]}  max={dr[1]}")

# 9. NULL rate on dirty cols
print("\n[9] NULL RATE (dirty-injected cols)")
nr1 = one(f"""SELECT COUNT(*) FILTER (WHERE warehouse_id IS NULL)*100.0/COUNT(*)
             FROM '{RAW}/data_inside_history.parquet'""")
nr2 = one(f"""SELECT COUNT(*) FILTER (WHERE vehicle_weight_kg IS NULL)*100.0/COUNT(*)
             FROM '{RAW}/data_transportation.parquet'""")
print(f"    inside_history.warehouse_id NULL:    {nr1:.2f}%  (ky vong ~5%)")
print(f"    transportation.vehicle_weight NULL:  {nr2:.2f}%  (ky vong ~2%)")

print("\n" + "="*70)
print("  VERIFICATION COMPLETE")
print("="*70)
