-- Engine: DuckDB
-- stg_district — passthrough clean. Bỏ cột denormalized province_name (lấy từ dim ở core)
with source as (
    select * from {{ source('raw', 'dim_district') }}
)

select
    cast(district_id as bigint)       as district_id,
    {{ clean_text('district_name') }} as district_name,
    cast(province_id as bigint)       as province_id
from source
