-- Engine: DuckDB
-- stg_cod — clean dirty data_cod (3M COD records):
--   amount kiểu DOUBLE → round về VND nguyên; dt VARCHAR → DATE. Loại heavy_issue.
--   discrepancy_amount = collected - cod (đối soát).
with source as (
    select * from {{ source('raw', 'data_cod') }}
    where {{ keep_non_quarantine('_data_quality') }}
)

select
    cast(cod_id as bigint)                          as cod_id,
    {{ clean_text('order_code') }}                  as order_code,
    cast(warehouse_id as bigint)                    as warehouse_id,
    cast(round(cod_amount) as bigint)               as cod_amount_vnd,
    cast(round(collected_amount) as bigint)         as collected_amount_vnd,
    cast(round(discrepancy_amount) as bigint)       as discrepancy_amount_vnd,
    lower(trim(cod_status))                         as cod_status,
    lower(trim(reconcile_status))                   as reconcile_status,
    cast(collect_time as timestamp)                 as collect_at,
    {{ parse_dt('dt') }}                            as dt,
    _data_quality,
    -- cờ đối soát: lệch tiền (sau khi đã collected)
    (cast(round(discrepancy_amount) as bigint) != 0) as has_discrepancy
from source
