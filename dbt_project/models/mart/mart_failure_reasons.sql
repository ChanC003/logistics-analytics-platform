-- Engine: DuckDB
-- mart_failure_reasons — top lý do giao thất bại theo vùng (từ fct_shipment attempt failed).
--   Dùng attempt-level (data_shipment) để bắt cả lần giao hỏng rồi giao lại thành công.
with s as (
    select * from {{ ref('fct_shipment') }}
    where is_failed and failure_reason is not null
),
total_failed as (
    select deliver_region, count(*) as region_failed
    from s group by 1
)

select
    coalesce(s.deliver_region, 'unknown')                        as region,
    s.failure_reason,
    count(*)                                                     as failed_attempts,
    count(distinct s.order_code)                                 as affected_orders,
    round(count(*) * 100.0 / nullif(t.region_failed, 0), 2)      as pct_of_region_failures
from s
left join total_failed t on s.deliver_region = t.deliver_region
group by 1, 2, t.region_failed
order by region, failed_attempts desc
