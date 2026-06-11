"""Quick smoke test — 500 orders, in-memory, verify pipeline end-to-end."""
import sys, time, io
sys.path.insert(0, '.')
# Fix Windows CP1252 terminal không encode được tiếng Việt
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print(">>> [1/8] Loading config...", flush=True)
import config as _cfg
_cfg.N_ORDERS = 500

print(">>> [2/8] Importing generators...", flush=True)
import dim_province, dim_district, dim_warehouse, dim_client, dim_shipper
import data_shippingorder_now, data_inside_history
import data_transportation, data_shipment, data_cod
print("    imports OK", flush=True)

print("\n>>> [3/8] Generating dims...", flush=True)
t0 = time.time()
prov = dim_province.generate(42)
print(f"    dim_province:  {len(prov):>6,} rows", flush=True)
dist = dim_district.generate(42, province_df=prov)
print(f"    dim_district:  {len(dist):>6,} rows", flush=True)
wh   = dim_warehouse.generate(42, district_df=dist)
print(f"    dim_warehouse: {len(wh):>6,} rows", flush=True)
cli  = dim_client.generate(42, district_df=dist)
print(f"    dim_client:    {len(cli):>6,} rows", flush=True)
shp  = dim_shipper.generate(42, warehouse_df=wh)
print(f"    dim_shipper:   {len(shp):>6,} rows", flush=True)
print(f"    dims done in {time.time()-t0:.2f}s", flush=True)

print("\n>>> [4/8] Generating data_shippingorder_now (500 orders)...", flush=True)
t0 = time.time()
orders = data_shippingorder_now.generate(42, district_df=dist, warehouse_df=wh, client_df=cli, shipper_df=shp)
print(f"    rows: {len(orders):,}  time: {time.time()-t0:.2f}s", flush=True)

print(f"    status:       {dict(orders['status'].value_counts().head(4))}", flush=True)
print(f"    _data_quality:{dict(orders['_data_quality'].value_counts())}", flush=True)

print("\n>>> [5/8] Generating data_inside_history...", flush=True)
t0 = time.time()
hist = data_inside_history.generate(42, order_df=orders, warehouse_df=wh, shipper_df=shp)
print(f"    rows: {len(hist):,}  time: {time.time()-t0:.2f}s  ratio: {len(hist)/len(orders):.1f}x/order", flush=True)
print(f"    action_category: {dict(hist['action_category'].value_counts(dropna=False).head(6))}", flush=True)
print(f"    _data_quality:   {dict(hist['_data_quality'].value_counts())}", flush=True)

print("\n>>> [6/8] Generating data_transportation...", flush=True)
t0 = time.time()
transp = data_transportation.generate(42, inside_df=hist, warehouse_df=wh, shipper_df=shp)
print(f"    rows: {len(transp):,}  time: {time.time()-t0:.2f}s", flush=True)
if len(transp):
    print(f"    avg packages/trip: {transp['n_packages'].mean():.1f}", flush=True)
print(f"    _data_quality: {dict(transp['_data_quality'].value_counts())}", flush=True)

print("\n>>> [7/8] Generating data_shipment...", flush=True)
t0 = time.time()
shpm = data_shipment.generate(42, order_df=orders, shipper_df=shp, warehouse_df=wh)
print(f"    rows: {len(shpm):,}  time: {time.time()-t0:.2f}s  ratio: {len(shpm)/len(orders):.2f}x/order", flush=True)
print(f"    attempt_status: {dict(shpm['attempt_status'].value_counts(dropna=False))}", flush=True)
print(f"    _data_quality:  {dict(shpm['_data_quality'].value_counts())}", flush=True)

print("\n>>> [8/8] Generating data_cod...", flush=True)
t0 = time.time()
cod = data_cod.generate(42, order_df=orders)
print(f"    rows: {len(cod):,}  time: {time.time()-t0:.2f}s", flush=True)
print(f"    cod_status:    {dict(cod['cod_status'].value_counts(dropna=False))}", flush=True)
print(f"    _data_quality: {dict(cod['_data_quality'].value_counts())}", flush=True)

print("\n" + "="*50, flush=True)
print("  SMOKE TEST PASSED", flush=True)
print("="*50, flush=True)
