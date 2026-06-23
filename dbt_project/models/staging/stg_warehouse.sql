-- Engine: DuckDB
-- stg_warehouse — clean dirty dim_warehouse:
--   district_id kiểu DOUBLE có NaN → to_bigint; TRIM name; bỏ province_name/region_fullname
--   denormalized (NULL nhiều) → core lấy lại từ dim_province
with source as (
    select * from {{ source('raw', 'dim_warehouse') }}
)

select
    cast(warehouse_id as bigint)        as warehouse_id,
    {{ clean_text('warehouse_name') }}  as warehouse_name,
    {{ clean_text('warehouse_type') }}  as warehouse_type,
    {{ to_bigint('district_id') }}      as district_id,
    cast(province_id as bigint)         as province_id,
    {{ clean_text('region_shortname') }} as region_shortname,
    cast(latitude as double)            as latitude,
    cast(longitude as double)           as longitude,
    cast(is_enabled as boolean)         as is_enabled,
    cast(is_virtual as boolean)         as is_virtual,
    cast(created_time as timestamp)     as created_time
from source
