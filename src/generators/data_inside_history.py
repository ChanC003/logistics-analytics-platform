"""
Generator: data_inside_history
Rows: ~40M (avg ~8 actions/order)
Output: data/raw/data_inside_history.parquet
Dependencies: data_shippingorder_now, dim_warehouse, dim_shipper
Fully vectorized — không có Python for-loop qua orders hay hops.
"""
from pathlib import Path
import numpy as np
import pandas as pd

from config import (
    KTC_ANCHORS,
    ACTIONS_PER_TRANSIT_HOP, ACTIONS_FINAL_HOP,
    TRUCK_TRIP_CODE_PREFIX, TRUCK_PACKAGES_PER_TRIP,
)
from _dirty import flag_quality

_KTC_IDS = np.array([k["warehouse_id"] for k in KTC_ANCHORS])
_CHARS   = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"))

_TRANSIT_ACTIONS = len(ACTIONS_PER_TRANSIT_HOP)   # 3: receive, pack, export
_FINAL_ACTIONS   = len(ACTIONS_FINAL_HOP)          # 2: receive, unpack

ACTION_NAME_MAP = {
    "receive": "receive_package",
    "pack":    "pack_to_bag",
    "unpack":  "unpack_bag",
    "export":  "export_to_truck",
    "return_receive": "return_receive",
    "return_export":  "return_export",
}


def _rand_codes(prefix: str, n: int, rng: np.random.Generator) -> np.ndarray:
    idx    = rng.integers(0, len(_CHARS), size=(n, 12))
    chars  = _CHARS[idx]          # (n, 12)
    # Fastest pure-numpy join: reduce + char.add across 12 columns
    joined = chars[:, 0].copy()
    for col in range(1, 12):
        joined = np.char.add(joined, chars[:, col])
    return np.char.add(prefix, joined)


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    order_df = kwargs.get("order_df")
    if order_df is None:
        order_df = pd.read_parquet("data/raw/data_shippingorder_now.parquet",
                                   columns=["order_code",
                                            "pick_warehouse_id", "deliver_warehouse_id",
                                            "created_date", "status"])

    wh_df = kwargs.get("warehouse_df")
    if wh_df is None:
        wh_df = pd.read_parquet("data/raw/dim_warehouse.parquet",
                                columns=["warehouse_id", "warehouse_type"])

    shipper_df = kwargs.get("shipper_df")
    if shipper_df is None:
        shipper_df = pd.read_parquet("data/raw/dim_shipper.parquet",
                                     columns=["shipper_id", "user_id"])

    bc_ids    = wh_df[wh_df["warehouse_type"] == "BC"]["warehouse_id"].values.astype(np.int64)
    user_ids  = shipper_df["user_id"].values
    user_names = np.array([f"NV{uid[:4]}" for uid in user_ids])

    order_df  = order_df.reset_index(drop=True)
    n_orders  = len(order_df)

    # ── Fill missing warehouse refs ───────────────────────────────────────────
    pick_wh_raw = order_df["pick_warehouse_id"].values
    del_wh_raw  = order_df["deliver_warehouse_id"].values
    null_pick   = pd.isna(pick_wh_raw)
    null_del    = pd.isna(del_wh_raw)
    pick_wh = np.where(null_pick, rng.choice(bc_ids, size=n_orders), pick_wh_raw).astype(np.int64)
    del_wh  = np.where(null_del,  rng.choice(bc_ids, size=n_orders), del_wh_raw).astype(np.int64)

    plv_raw  = np.full(n_orders, "Noi Vung")  # placeholder — phanloaivung do dbt tính
    statuses = order_df["status"].fillna("").values
    base_dates = pd.to_datetime(order_df["created_date"]).values.astype("datetime64[ns]")

    # ── n_transit per order (vectorized) ─────────────────────────────────────
    n_transit = np.where(plv_raw == "Nội Tỉnh", 1,
                np.where(plv_raw == "Nội Vùng", 2, 3)).astype(np.int64)
    lv_mask = plv_raw == "Liên Vùng"
    if lv_mask.sum() > 0:
        n_transit[lv_mask] = rng.choice([2, 3, 4], size=lv_mask.sum(), p=[0.40, 0.40, 0.20])

    # ── Build wh_chain columns vectorized ────────────────────────────────────
    # Max hops = 4, so max intermediate KTCs = 3
    # Pre-generate all KTC slots, fill only where needed
    max_hops   = int(n_transit.max())
    total_hops = int(n_transit.sum())

    # hop_start[i] = index of first hop for order i
    hop_start = np.zeros(n_orders + 1, dtype=np.int64)
    hop_start[1:] = np.cumsum(n_transit)

    # order_hop_idx[j] = which order hop j belongs to
    order_hop_idx = np.repeat(np.arange(n_orders, dtype=np.int64), n_transit)
    hop_local_idx = np.concatenate([np.arange(h, dtype=np.int64) for h in n_transit])
    is_final_hop  = hop_local_idx == (n_transit[order_hop_idx] - 1)

    # Assign KTC nodes: for each hop that needs an intermediate KTC
    # hop 0 always from pick_wh; hop final always to del_wh
    # intermediate nodes = hops 1..n-2 in each order → KTC
    ktc_assignments = rng.choice(_KTC_IDS, size=total_hops)  # upper bound, most unused

    wh_from_all = np.zeros(total_hops, dtype=np.int64)
    wh_to_all   = np.zeros(total_hops, dtype=np.int64)

    # Vectorized chain build using segment logic:
    # For each hop j of order i:
    #   wh_from[j] = pick_wh[i]          if hop_local=0
    #              = ktc_assignments[j-1] if 0 < hop_local < n_transit-1
    #              = ktc_assignments[j-1] if hop_local == n_transit-1 and n_transit > 1
    # Simpler: build "node" array of length (n_orders × (max_hops+1)) then slice

    # For each hop j, from = node[j], to = node[j+1]
    # node[hop_start[i]+0]          = pick_wh[i]
    # node[hop_start[i]+n_transit[i]] = del_wh[i]
    # node[hop_start[i]+1 .. n_transit[i]-1] = KTC

    nodes = np.zeros(total_hops + n_orders, dtype=np.int64)  # one extra per order for del_wh
    # node positions: for order i, nodes are at hop_start[i]..hop_start[i]+n_transit[i]
    # (n_transit[i]+1 nodes per order)
    node_start = np.zeros(n_orders + 1, dtype=np.int64)
    node_start[1:] = np.cumsum(n_transit + 1)
    total_nodes = int(node_start[-1])
    nodes = np.zeros(total_nodes, dtype=np.int64)

    # Set first and last node per order (vectorized)
    nodes[node_start[:-1]]              = pick_wh   # first node = pick_wh
    nodes[node_start[:-1] + n_transit]  = del_wh    # last node  = del_wh

    # Set intermediate KTC nodes
    # intermediate positions: node_start[i]+1 .. node_start[i]+n_transit[i]-1
    n_intermediate = np.maximum(0, n_transit - 1)
    total_intermediate = int(n_intermediate.sum())
    ktc_pool = rng.choice(_KTC_IDS, size=total_intermediate)
    ktc_cursor = 0
    for i in range(n_orders):
        ni = int(n_intermediate[i])
        if ni > 0:
            s = int(node_start[i]) + 1
            nodes[s:s + ni] = ktc_pool[ktc_cursor:ktc_cursor + ni]
            ktc_cursor += ni

    # Extract wh_from / wh_to per hop
    for i in range(n_orders):
        s_hop  = int(hop_start[i])
        s_node = int(node_start[i])
        nh     = int(n_transit[i])
        wh_from_all[s_hop:s_hop + nh] = nodes[s_node:s_node + nh]
        wh_to_all  [s_hop:s_hop + nh] = nodes[s_node + 1:s_node + nh + 1]

    # hop-level arrays (length = total_hops)
    base_times_per_hop   = base_dates[order_hop_idx]
    order_codes_per_hop  = order_df["order_code"].values[order_hop_idx]

    # ── Expand hops → action rows (vectorized) ────────────────────────────────
    n_actions_each = np.where(is_final_hop, _FINAL_ACTIONS, _TRANSIT_ACTIONS).astype(np.int64)
    total_rows     = int(n_actions_each.sum())

    # action_start[j] = row index of first action for hop j
    action_start = np.zeros(total_hops + 1, dtype=np.int64)
    action_start[1:] = np.cumsum(n_actions_each)

    hop_of_row = np.repeat(np.arange(total_hops, dtype=np.int64), n_actions_each)

    # Expand hop-level → row-level
    base_times_hops  = base_times_per_hop[hop_of_row]
    order_codes_hops = order_codes_per_hop[hop_of_row]

    # action_pos vectorized: dùng cumsum thay vì list comprehension
    action_pos = np.arange(total_rows, dtype=np.int64) - action_start[hop_of_row]

    is_final_row = is_final_hop[hop_of_row]

    TRANSIT_CATS = np.array(ACTIONS_PER_TRANSIT_HOP)
    FINAL_CATS   = np.array(ACTIONS_FINAL_HOP)
    pos_clip_t   = action_pos.clip(0, _TRANSIT_ACTIONS - 1)
    pos_clip_f   = action_pos.clip(0, _FINAL_ACTIONS - 1)
    categories   = np.where(is_final_row, FINAL_CATS[pos_clip_f], TRANSIT_CATS[pos_clip_t])

    # action_names: vectorized map qua pd.Series (nhanh hơn list comprehension)
    _NAME_SERIES = pd.Series(ACTION_NAME_MAP)
    action_names = _NAME_SERIES.reindex(categories).values

    # Timestamps: vectorized cumsum per hop group
    offsets_min  = rng.integers(10, 90, size=total_rows).astype(np.int64)
    hop_base_min = rng.integers(60, 240, size=total_hops).astype(np.int64)
    # hop_base broadcast to rows
    hop_base_rep = hop_base_min[hop_of_row]
    # cumsum within each hop: use global cumsum then subtract hop start
    global_cum   = np.cumsum(offsets_min)
    hop_cum_start = np.zeros(total_rows, dtype=np.int64)
    hop_cum_start = global_cum - global_cum[action_start[hop_of_row]]
    minutes_offset = hop_base_rep + hop_cum_start
    action_times = base_times_hops[hop_of_row] + (minutes_offset * 60 * 10**9).astype("timedelta64[ns]")

    uid_idx      = rng.integers(0, len(user_ids), size=total_rows)
    is_receive   = categories == "receive"
    wh_from_rep  = wh_from_all[hop_of_row]
    wh_to_rep    = wh_to_all[hop_of_row]
    warehouse_ids = np.where(is_receive, wh_to_rep, wh_from_rep).astype(np.float64)

    # trip_code on export rows only — gom theo (from_wh, to_wh, date_bucket, capacity)
    # so that ~TRUCK_PACKAGES_PER_TRIP exports share the same trip_code
    is_export  = categories == "export"
    trip_codes = np.full(total_rows, None, dtype=object)
    n_exp      = int(is_export.sum())
    if n_exp > 0:
        exp_from = wh_from_rep[is_export].astype(np.int64)
        exp_to   = wh_to_rep[is_export].astype(np.int64)
        # Gom theo (from, to, date): mỗi route/ngày 1 chuyến. Mạng 2,000 kho →
        # long-tail: route trung tâm gom đầy 20 kiện, route BC nhỏ chỉ 1-2 kiện.
        exp_date = base_times_hops[is_export].astype("datetime64[D]").astype(np.int64)
        # Sort by (from, to, date) — same-route same-day consecutive
        sort_key = exp_from * 10**12 + exp_to * 10**6 + exp_date
        sort_idx = np.argsort(sort_key, kind="stable")
        sorted_key = sort_key[sort_idx]

        # Break points: new route OR every TRUCK_PACKAGES_PER_TRIP within same route
        cap = TRUCK_PACKAGES_PER_TRIP
        route_changed = np.empty(n_exp, dtype=bool)
        route_changed[0] = True
        route_changed[1:] = sorted_key[1:] != sorted_key[:-1]
        # Within-route running counter — reset at each route change
        route_group_id = np.cumsum(route_changed) - 1   # group per unique route
        # position within route group (0, 1, 2, ... reset each route)
        route_start_pos = np.zeros(n_exp, dtype=np.int64)
        route_start_pos[route_changed] = np.arange(route_changed.sum(), dtype=np.int64)
        # broadcast start position of each route to all its members
        route_start_pos = np.maximum.accumulate(
            np.where(route_changed, np.arange(n_exp, dtype=np.int64), 0)
        )
        pos_in_route = np.arange(n_exp, dtype=np.int64) - route_start_pos
        # Force new trip at capacity boundaries
        cap_break = (pos_in_route % cap == 0)
        trip_group = np.cumsum(route_changed | cap_break) - 1

        # Restore original export order
        trip_group_orig = np.empty(n_exp, dtype=np.int64)
        trip_group_orig[sort_idx] = trip_group

        n_trips = int(trip_group_orig.max()) + 1
        trip_pool = _rand_codes(TRUCK_TRIP_CODE_PREFIX, n_trips, rng)
        trip_codes[is_export] = trip_pool[trip_group_orig]

    # package_code + session_code: one per hop, expanded to rows
    pkg_per_hop  = _rand_codes("P", total_hops, rng)
    sess_per_hop = _rand_codes("S", total_hops, rng)
    pkg_codes    = pkg_per_hop[hop_of_row]
    sess_codes   = sess_per_hop[hop_of_row]

    dt_col = pd.to_datetime(action_times).strftime("%Y-%m-%d").to_numpy()

    df = pd.DataFrame({
        "dt":                dt_col,
        "action_time":       action_times,
        "action_category":   categories,
        "action_name":       action_names,
        "package_code":      pkg_codes,
        "order_code":        order_codes_hops,
        "warehouse_id":      warehouse_ids,
        "from_warehouse_id": wh_from_rep.astype(np.float64),
        "to_warehouse_id":   wh_to_rep.astype(np.float64),
        "trip_code":         trip_codes,
        "trip_partner":      None,
        "stop_code":         None,
        "session_code":      sess_codes,
        "user_id":           user_ids[uid_idx],
        "user_name":         user_names[uid_idx],
        "_data_quality":     "clean",
    })

    # ── Return actions (return_to_sender orders) ──────────────────────────────
    ret_mask = statuses == "return_to_sender"
    n_ret    = int(ret_mask.sum())
    if n_ret > 0:
        ret_order_codes = order_df["order_code"].values[ret_mask]
        ret_del  = del_wh[ret_mask]
        ret_pick = pick_wh[ret_mask]
        ret_base = base_dates[ret_mask]

        # 2 actions per return order: return_receive, return_export
        ret_order_rep = np.repeat(ret_order_codes, 2)
        ret_del_rep   = np.repeat(ret_del, 2)
        ret_pick_rep  = np.repeat(ret_pick, 2)
        ret_base_rep  = np.repeat(ret_base, 2)
        ret_act_pos   = np.tile([0, 1], n_ret)
        ret_cats      = np.where(ret_act_pos == 0, "return_receive", "return_export")
        ret_offset    = rng.integers(6*60, 36*60, size=n_ret*2).astype(np.int64)
        ret_times     = ret_base_rep + (ret_offset * 60 * 10**9).astype("timedelta64[ns]")
        ret_pkg       = np.repeat(_rand_codes("P", n_ret, rng), 2)
        ret_sess      = np.repeat(_rand_codes("S", n_ret, rng), 2)
        ret_uid       = rng.integers(0, len(user_ids), size=n_ret * 2)

        ret_df = pd.DataFrame({
            "dt":                pd.to_datetime(ret_times).strftime("%Y-%m-%d"),
            "action_time":       ret_times,
            "action_category":   ret_cats,
            "action_name":       ret_cats,
            "package_code":      ret_pkg,
            "order_code":        ret_order_rep,
            "warehouse_id":      ret_del_rep.astype(np.float64),
            "from_warehouse_id": ret_del_rep.astype(np.float64),
            "to_warehouse_id":   ret_pick_rep.astype(np.float64),
            "trip_code":         None,
            "trip_partner":      None,
            "stop_code":         None,
            "session_code":      ret_sess,
            "user_id":           user_ids[ret_uid],
            "user_name":         user_names[ret_uid],
            "_data_quality":     "clean",
        })
        df = pd.concat([df, ret_df], ignore_index=True)

    # ── Dirty inject ──────────────────────────────────────────────────────────
    n     = len(df)
    heavy = pd.Series(False, index=df.index)
    light = pd.Series(False, index=df.index)

    null_ac = pd.Series(rng.random(n) < 0.01, index=df.index)
    df["action_category"] = df["action_category"].astype(object)
    df["action_name"]     = df["action_name"].astype(object)
    df.loc[null_ac, "action_category"] = None
    df.loc[null_ac, "action_name"]     = None
    heavy |= null_ac

    null_wh = pd.Series(rng.random(n) < 0.05, index=df.index)
    df["warehouse_id"] = df["warehouse_id"].astype(object)
    df.loc[null_wh, "warehouse_id"] = None
    light |= null_wh

    df = flag_quality(df, heavy, light)
    return df


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    import sys, time
    sample = "--sample" in sys.argv
    order_df = pd.read_parquet("data/raw/data_shippingorder_now.parquet",
                               columns=["order_code",
                                        "pick_warehouse_id", "deliver_warehouse_id",
                                        "created_date", "status"])
    if sample:
        order_df = order_df.head(10_000)
    t0 = time.time()
    df = generate(order_df=order_df)
    print(f"data_inside_history: {len(df):,} rows in {time.time()-t0:.1f}s")
    write(df, Path("data/raw/data_inside_history.parquet"))
