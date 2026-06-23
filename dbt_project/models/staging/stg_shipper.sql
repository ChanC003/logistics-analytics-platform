-- Engine: DuckDB
-- stg_shipper — clean dirty dim_shipper: plate format bẩn, future hire_date.
--   GIỮ heavy_issue (4 row): đây là DIMENSION — drop key sẽ orphan fact tham chiếu tới.
--   Chỉ clean ATTRIBUTE, không drop key. hire_date tương lai → clamp NULL (giữ cờ để audit).
with source as (
    select * from {{ source('raw', 'dim_shipper') }}
)

select
    cast(shipper_id as bigint)             as shipper_id,
    {{ clean_text('user_id') }}            as user_id,
    cast(warehouse_id as bigint)           as warehouse_id,
    cast(province_id as bigint)            as province_id,
    -- hire_date tương lai (dirty) → coi như NULL, nhưng giữ cờ has_future_hire_date
    case when hire_date > current_date then null else cast(hire_date as date) end as hire_date,
    (hire_date > current_date)             as has_future_hire_date,
    cast(is_active as boolean)             as is_active,
    {{ clean_text('performance_tier') }}   as performance_tier,
    -- chuẩn hoá biển số: upper + bỏ khoảng trắng thừa
    upper(regexp_replace(trim(coalesce(truck_plate_number, '')), '\s+', '', 'g')) as truck_plate_number,
    cast(vehicle_weight_kg as double)      as vehicle_weight_kg,
    _data_quality
from source
