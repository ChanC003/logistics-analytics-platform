-- Engine: DuckDB
-- dim_district — join lấy lại province_name + region (denormalize cho tiện query mart)
with d as (
    select * from {{ ref('stg_district') }}
),
p as (
    select * from {{ ref('stg_province') }}
)

select
    d.district_id,
    d.district_name,
    d.province_id,
    p.province_name,
    p.region
from d
left join p on d.province_id = p.province_id
