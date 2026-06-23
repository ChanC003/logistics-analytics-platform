-- Engine: DuckDB
-- fct_shipment — fact lastmile attempt (grain: 1 attempt). trip_code prefix 'L'.
--   Join region kho giao. is_success/is_failed từ attempt_status.
with s as (
    select * from {{ ref('stg_shipment') }}
),
wh as (select warehouse_id, region from {{ ref('dim_warehouse') }})

select
    s.trip_code,
    s.order_code,
    s.attempt_no,
    s.dt,
    cast(strftime(s.dt, '%Y%m%d') as integer) as date_id,
    s.shipper_id,
    s.shipper_user_id,
    s.deliver_warehouse_id,
    wh.region                                 as deliver_region,
    s.deliver_shift,
    s.attempt_status,
    s.attempt_result,
    (s.attempt_status = 'success')            as is_success,
    (s.attempt_status = 'failed')             as is_failed,
    s.failure_reason,
    s.deliver_at,
    s._data_quality
from s
left join wh on s.deliver_warehouse_id = wh.warehouse_id
