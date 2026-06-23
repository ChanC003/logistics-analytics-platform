-- Engine: DuckDB
-- mart_sla_breakdown — phân tích SLA theo tuần × vùng × loại dịch vụ:
--   breach rate + leadtime phân vị (p50/p90) để thấy đuôi chậm.
with o as (
    select * from {{ ref('fct_shipping_order') }}
    where is_delivered  -- SLA chỉ tính trên đơn đã giao xong
),
d as (
    select date_id, week_start, year, quarter from {{ ref('dim_date') }}
)

select
    d.week_start,
    d.year,
    d.quarter,
    coalesce(o.deliver_region, 'unknown')                        as region,
    coalesce(o.type_order_code, 'unknown')                       as service_code,
    count(*)                                                     as delivered_orders,
    count(*) filter (where o.is_sla_breach)                      as sla_breach_orders,
    round(count(*) filter (where o.is_sla_breach) * 100.0 / nullif(count(*), 0), 2) as sla_breach_rate_pct,
    round(avg(o.delivery_hours), 2)                              as avg_delivery_hours,
    round(median(o.delivery_hours), 2)                           as p50_delivery_hours,
    round(quantile_cont(o.delivery_hours, 0.9), 2)               as p90_delivery_hours
from o
inner join d on o.date_id = d.date_id
group by 1, 2, 3, 4, 5
