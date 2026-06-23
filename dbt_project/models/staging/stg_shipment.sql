-- Engine: DuckDB
-- stg_shipment — clean dirty data_shipment (6.1M lastmile attempts):
--   trip_code prefix 'L' (KHÁC transportation 'T' — KHÔNG join chéo).
--   deliver_warehouse_id DOUBLE → to_bigint; dt VARCHAR → DATE. Loại heavy_issue.
with source as (
    select * from {{ source('raw', 'data_shipment') }}
    where {{ keep_non_quarantine('_data_quality') }}
)

select
    {{ clean_text('trip_code') }}           as trip_code,
    {{ clean_text('order_code') }}          as order_code,
    cast(attempt_no as integer)             as attempt_no,
    cast(shipper_id as bigint)              as shipper_id,
    {{ clean_text('shipper_user_id') }}     as shipper_user_id,
    {{ to_bigint('deliver_warehouse_id') }} as deliver_warehouse_id,
    {{ clean_text('deliver_shift') }}       as deliver_shift,
    lower(trim(attempt_status))             as attempt_status,
    {{ clean_text('attempt_result') }}      as attempt_result,
    {{ clean_text('failure_reason') }}      as failure_reason,
    cast(deliver_time as timestamp)         as deliver_at,
    {{ parse_dt('dt') }}                    as dt,
    _data_quality
from source
