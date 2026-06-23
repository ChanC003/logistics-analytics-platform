-- Engine: DuckDB
-- dim_warehouse — fill lại province_name/region từ dim_province (raw bị NULL nhiều)
with w as (
    select * from {{ ref('stg_warehouse') }}
),
p as (
    select * from {{ ref('stg_province') }}
)

select
    w.warehouse_id,
    w.warehouse_name,
    w.warehouse_type,
    w.district_id,
    w.province_id,
    p.province_name,
    p.region,
    w.region_shortname,
    w.latitude,
    w.longitude,
    w.is_enabled,
    w.is_virtual,
    w.created_time
from w
left join p on w.province_id = p.province_id
