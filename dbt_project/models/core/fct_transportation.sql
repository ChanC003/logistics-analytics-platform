-- Engine: DuckDB
-- fct_transportation — fact truck trip line-haul (grain: 1 trip_code 'T').
--   Join region 2 đầu (from/to warehouse) để phân tích tuyến vận tải.
with t as (
    select * from {{ ref('stg_transportation') }}
),
wf as (select warehouse_id, region as from_region from {{ ref('dim_warehouse') }}),
wt as (select warehouse_id, region as to_region   from {{ ref('dim_warehouse') }})

select
    t.trip_code,
    t.dt,
    cast(strftime(t.dt, '%Y%m%d') as integer) as date_id,
    t.from_warehouse_id,
    wf.from_region,
    t.to_warehouse_id,
    wt.to_region,
    (wf.from_region = wt.to_region)           as is_intra_region,
    t.driver_shipper_id,
    t.truck_plate_number,
    t.vehicle_weight_kg,
    t.n_packages,
    t.departure_at,
    t.arrival_at,
    t.transit_hours,
    t._data_quality
from t
left join wf on t.from_warehouse_id = wf.warehouse_id
left join wt on t.to_warehouse_id = wt.warehouse_id
