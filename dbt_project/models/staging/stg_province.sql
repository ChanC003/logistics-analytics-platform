-- Engine: DuckDB
-- stg_province — passthrough clean (dim_province không có dirty)
with source as (
    select * from {{ source('raw', 'dim_province') }}
)

select
    cast(province_id as bigint)   as province_id,
    {{ clean_text('province_name') }} as province_name,
    {{ clean_text('region') }}        as region,
    cast(region_idx as integer)   as region_idx
from source
