-- Engine: DuckDB
-- dim_date — passthrough + thêm week_start (DATE) để mart partition theo tuần (CLAUDE.md §3)
select
    date_id,
    date_day,
    -- week_start = thứ 2 đầu tuần (ISO) — dùng cho mart partition theo week_start
    date_trunc('week', date_day)        as week_start,
    year,
    quarter,
    month,
    week_of_year,
    day_of_week,
    day_of_week_vn,
    is_weekend,
    is_holiday_vn
from {{ ref('stg_date') }}
