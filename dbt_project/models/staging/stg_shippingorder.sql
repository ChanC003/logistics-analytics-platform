-- Engine: DuckDB
-- stg_shippingorder — clean dirty data_shippingorder_now (5M):
--   1. DEDUP order_code (2,562 dup CỐ Ý — dirty S9): giữ row created_date mới nhất
--   2. Normalize enum status (DONE/FINISH → delivered)
--   3. Loại heavy_issue khỏi luồng chính
--   4. Cast cod_collect_date VARCHAR → timestamp
with source as (
    select * from {{ source('raw', 'data_shippingorder_now') }}
    where {{ keep_non_quarantine('_data_quality') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by order_code
            order by created_date desc nulls last
        ) as _rn
    from source
)

select
    {{ clean_text('order_code') }}            as order_code,
    cast(shop_id as bigint)                   as shop_id,
    cast(client_id as bigint)                 as client_id,
    cast(from_district_id as bigint)          as from_district_id,
    cast(to_district_id as bigint)            as to_district_id,
    {{ clean_text('from_ward_code') }}        as from_ward_code,
    {{ clean_text('to_ward_code') }}          as to_ward_code,
    cast(weight as bigint)                    as weight_gram,
    cast(length as bigint)                    as length_cm,
    cast(width as bigint)                     as width_cm,
    cast(height as bigint)                    as height_cm,
    cast(converted_weight as bigint)          as converted_weight_gram,
    cast(service_type_id as bigint)           as service_type_id,
    cast(service_id as bigint)                as service_id,
    cast(cod_amount as bigint)                as cod_amount_vnd,
    try_cast(cod_collect_date as timestamp)   as cod_collect_at,
    cast(insurance_value as bigint)           as insurance_value_vnd,
    cast(pick_station_id as bigint)           as pick_station_id,
    {{ clean_text('content') }}               as content,
    {{ clean_text('created_source') }}        as created_source,
    cast(created_date as timestamp)           as created_at,
    cast(dt as date)                          as dt,
    cast(date_id as integer)                  as date_id,
    {{ normalize_order_status('status') }}    as status,
    {{ order_outcome_group(normalize_order_status('status')) }} as outcome_group,
    cast(pick_warehouse_id as bigint)         as pick_warehouse_id,
    cast(deliver_warehouse_id as bigint)      as deliver_warehouse_id,
    cast(current_warehouse_id as bigint)      as current_warehouse_id,
    {{ to_bigint('return_warehouse_id') }}    as return_warehouse_id,
    {{ clean_text('deliver_shift') }}         as deliver_shift,
    cast(pick_user as bigint)                 as pick_user_id,
    cast(deliver_user as bigint)              as deliver_user_id,
    {{ to_bigint('return_user') }}            as return_user_id,
    cast(end_pick_time as timestamp)          as end_pick_at,
    cast(first_delivered_time as timestamp)   as first_delivered_at,
    cast(end_delivery_time as timestamp)      as end_delivery_at,
    cast(cod_failed_amount as bigint)         as cod_failed_amount_vnd,
    cast(is_b2b as boolean)                   as is_b2b,
    {{ clean_text('type_order') }}            as type_order,
    {{ clean_text('type_order_code') }}       as type_order_code,
    cast(is_sla_breach as boolean)            as is_sla_breach,
    {{ clean_text('failure_reason') }}        as failure_reason,
    _data_quality,
    -- delivery leadtime (giờ) = first_delivered - created. NULL nếu chưa giao
    case
        when first_delivered_time is not null and created_date is not null
        then date_diff('second', cast(created_date as timestamp), cast(first_delivered_time as timestamp)) / 3600.0
    end                                       as delivery_hours
from deduped
where _rn = 1
