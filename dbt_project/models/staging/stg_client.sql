-- Engine: DuckDB
-- stg_client — clean dirty dim_client (light_issue ~1%). DIMENSION → giữ mọi key
-- (kể cả heavy_issue) để fact không bị orphan; chỉ clean attribute.
with source as (
    select * from {{ source('raw', 'dim_client') }}
)

select
    cast(client_id as bigint)        as client_id,
    cast(shop_id as bigint)          as shop_id,
    {{ clean_text('client_type') }}  as client_type,
    cast(province_id as bigint)      as province_id,
    cast(district_id as bigint)      as district_id,
    cast(is_b2b as boolean)          as is_b2b,
    cast(created_date as date)       as created_date,
    {{ clean_text('tier') }}         as tier,
    _data_quality
from source
