-- Engine: DuckDB
-- dim_shipper — join warehouse + province; tenure_days từ hire_date
with s as (
    select * from {{ ref('stg_shipper') }}
),
w as (
    select warehouse_id, warehouse_name, region from {{ ref('dim_warehouse') }}
),
p as (
    select province_id, province_name, region as province_region from {{ ref('stg_province') }}
)

select
    s.shipper_id,
    s.user_id,
    s.warehouse_id,
    w.warehouse_name,
    w.region,
    s.province_id,
    p.province_name,
    s.hire_date,
    s.has_future_hire_date,
    case when s.hire_date is not null
         then date_diff('day', s.hire_date, current_date) end as tenure_days,
    s.is_active,
    s.performance_tier,
    s.truck_plate_number,
    s.vehicle_weight_kg
from s
left join w on s.warehouse_id = w.warehouse_id
left join p on s.province_id = p.province_id
