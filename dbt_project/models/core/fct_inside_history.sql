-- Engine: DuckDB
-- fct_inside_history — fact package events (grain: 1 event). 41M rows — table lớn nhất.
--   Passthrough từ staging (đã clean type). Thêm date_id để join dim_date ở mart.
select
    package_code,
    order_code,
    dt,
    cast(strftime(dt, '%Y%m%d') as integer)  as date_id,
    action_at,
    action_category,
    action_name,
    warehouse_id,
    from_warehouse_id,
    to_warehouse_id,
    trip_code,
    session_code,
    user_id,
    _data_quality
from {{ ref('stg_inside_history') }}
