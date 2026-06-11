"""
Orchestrator: chạy tất cả generators theo đúng dependency order.

Usage:
  python generate_all.py                   # seed=42, full dataset
  python generate_all.py --seed 99         # custom seed
  python generate_all.py --sample          # 10k orders để test nhanh
  python generate_all.py --only dim        # chỉ chạy các dim table
  python generate_all.py --skip cod        # bỏ qua cod generator
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd

# Ensure generators/ is on path khi gọi từ thư mục khác
sys.path.insert(0, str(Path(__file__).parent))

import dim_province
import dim_district
import dim_date
import dim_warehouse
import dim_client
import dim_shipper
import data_shippingorder_now
import data_inside_history
import data_transportation
import data_shipment
import data_cod

RAW = Path(__file__).parent.parent.parent / "data" / "raw"
SAMPLE_DIR = Path(__file__).parent.parent.parent / "data" / "sample"

GENERATORS = [
    ("dim_province",          dim_province),
    ("dim_district",          dim_district),
    ("dim_date",              dim_date),
    ("dim_warehouse",         dim_warehouse),
    ("dim_client",            dim_client),
    ("dim_shipper",           dim_shipper),
    ("data_shippingorder_now", data_shippingorder_now),
    ("data_inside_history",   data_inside_history),
    ("data_transportation",   data_transportation),
    ("data_shipment",         data_shipment),
    ("data_cod",              data_cod),
]

DIM_NAMES = {"dim_province", "dim_district", "dim_date",
             "dim_warehouse", "dim_client", "dim_shipper"}


def parse_args():
    p = argparse.ArgumentParser(description="Run all logistics data generators")
    p.add_argument("--seed",   type=int, default=42, help="Random seed (default 42)")
    p.add_argument("--sample", action="store_true",  help="Run with 10k orders (fast verify)")
    p.add_argument("--only",   type=str, default=None,
                   help="Run only generators matching this substring (e.g. 'dim', 'cod')")
    p.add_argument("--skip",   type=str, default=None,
                   help="Skip generators matching this substring")
    return p.parse_args()


def run(args):
    seed    = args.seed
    sample  = args.sample
    RAW.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  Logistics Data Generator  |  seed={seed}  |  {'SAMPLE' if sample else 'FULL'}")
    print(f"{'='*60}\n")

    # ── Dependency cache ──────────────────────────────────────────────────────
    cache = {}
    results = {}

    def load_or_gen(name, mod, extra_kwargs=None):
        if name in cache:
            return cache[name]
        kw = extra_kwargs or {}
        t0 = time.time()
        df = mod.generate(seed=seed, **kw)
        elapsed = time.time() - t0
        out_path = RAW / f"{name}.parquet"
        mod.write(df, out_path)
        print(f"  [{elapsed:5.1f}s] {name:<30} {len(df):>10,} rows  →  {out_path.name}")
        cache[name] = df
        results[name] = {"rows": len(df), "path": str(out_path)}
        return df

    t_total = time.time()

    for name, mod in GENERATORS:
        # --only / --skip filters
        if args.only and args.only.lower() not in name.lower():
            continue
        if args.skip and args.skip.lower() in name.lower():
            print(f"  [SKIP] {name}")
            continue

        # Inject trước nếu đã build
        kw = {}
        if name == "dim_district":
            if "dim_province" in cache:
                kw["province_df"] = cache["dim_province"]
        elif name == "dim_warehouse":
            for k in ("dim_district",):
                if k in cache: kw["district_df"] = cache[k]
        elif name == "dim_client":
            if "dim_district" in cache: kw["district_df"] = cache["dim_district"]
        elif name == "dim_shipper":
            if "dim_warehouse" in cache: kw["warehouse_df"] = cache["dim_warehouse"]
        elif name == "data_shippingorder_now":
            for k, alias in [("dim_district","district_df"), ("dim_warehouse","warehouse_df"),
                              ("dim_client","client_df"),    ("dim_shipper","shipper_df")]:
                if k in cache: kw[alias] = cache[k]
            if sample:
                # Patch N_ORDERS to 10k for fast verify
                import config as _cfg
                _cfg.N_ORDERS = 10_000
        elif name == "data_inside_history":
            if "data_shippingorder_now" in cache:
                order_df = cache["data_shippingorder_now"]
                if sample: order_df = order_df.head(10_000)
                kw["order_df"] = order_df
            if "dim_warehouse" in cache: kw["warehouse_df"] = cache["dim_warehouse"]
            if "dim_shipper"   in cache: kw["shipper_df"]   = cache["dim_shipper"]
        elif name == "data_transportation":
            if "data_inside_history" in cache: kw["inside_df"]   = cache["data_inside_history"]
            if "dim_warehouse"       in cache: kw["warehouse_df"] = cache["dim_warehouse"]
            if "dim_shipper"         in cache: kw["shipper_df"]   = cache["dim_shipper"]
        elif name == "data_shipment":
            if "data_shippingorder_now" in cache:
                order_df = cache["data_shippingorder_now"]
                kw["order_df"] = order_df
            if "dim_shipper"   in cache: kw["shipper_df"]   = cache["dim_shipper"]
            if "dim_warehouse" in cache: kw["warehouse_df"] = cache["dim_warehouse"]
        elif name == "data_cod":
            if "data_shippingorder_now" in cache: kw["order_df"] = cache["data_shippingorder_now"]

        load_or_gen(name, mod, kw)

    elapsed_total = time.time() - t_total

    # ── Sample 50k ─────────────────────────────────────────────────────────────
    if not sample and "data_shippingorder_now" in cache:
        print("\n  Writing sample 50k rows …")
        sample_df = cache["data_shippingorder_now"].sample(50_000, random_state=seed)
        sample_path = SAMPLE_DIR / "data_shippingorder_sample.parquet"
        sample_df.to_parquet(sample_path, compression="snappy", index=False)
        print(f"  Sample → {sample_path}")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Done in {elapsed_total:.1f}s  |  {len(results)} tables generated")
    total_rows = sum(v["rows"] for v in results.values())
    print(f"  Total rows: {total_rows:,}")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    args = parse_args()
    run(args)
