-- Engine: DuckDB
-- stg_inside_history — clean dirty data_inside_history (41M, file lớn nhất):
--   warehouse_id/from/to kiểu DOUBLE nullable → to_bigint; dt VARCHAR → DATE.
--   Loại heavy_issue. KHÔNG dedup (event log — trùng package+action là hợp lệ).
with source as (
    select * from {{ source('raw', 'data_inside_history') }}
    where {{ keep_non_quarantine('_data_quality') }}
)

select
    {{ parse_dt('dt') }}                  as dt,
    cast(action_time as timestamp)        as action_at,
    {{ clean_text('action_category') }}   as action_category,
    {{ clean_text('action_name') }}       as action_name,
    {{ clean_text('package_code') }}      as package_code,
    {{ clean_text('order_code') }}        as order_code,
    {{ to_bigint('warehouse_id') }}       as warehouse_id,
    {{ to_bigint('from_warehouse_id') }}  as from_warehouse_id,
    {{ to_bigint('to_warehouse_id') }}    as to_warehouse_id,
    {{ clean_text('trip_code') }}         as trip_code,
    cast(trip_partner as integer)         as trip_partner,
    cast(stop_code as integer)            as stop_code,
    {{ clean_text('session_code') }}      as session_code,
    {{ clean_text('user_id') }}           as user_id,
    {{ clean_text('user_name') }}         as user_name,
    _data_quality
from source
