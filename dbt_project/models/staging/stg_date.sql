-- Engine: DuckDB
-- stg_date — passthrough clean
with source as (
    select * from {{ source('raw', 'dim_date') }}
)

select
    cast(date_id as integer)        as date_id,
    cast("date" as date)            as date_day,
    cast(year as integer)           as year,
    cast(quarter as integer)        as quarter,
    cast(month as integer)          as month,
    cast(week_of_year as integer)   as week_of_year,
    cast(day_of_week as integer)    as day_of_week,
    {{ clean_text('day_of_week_vn') }} as day_of_week_vn,
    cast(is_weekend as boolean)     as is_weekend,
    cast(is_holiday_vn as boolean)  as is_holiday_vn
from source
