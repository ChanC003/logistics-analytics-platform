-- Engine: DuckDB
-- mart_daily_kpi — KPI vận hành theo ngày × vùng giao:
--   tổng đơn, success rate, return rate, SLA breach rate, COD value, avg leadtime.
with o as (
    select * from {{ ref('fct_shipping_order') }}
),
d as (
    select date_id, date_day, week_start, year, quarter, month, day_of_week_vn, is_weekend, is_holiday_vn
    from {{ ref('dim_date') }}
),
agg as (
    select
        o.date_id,
        coalesce(o.deliver_region, 'unknown')                          as region,
        count(*)                                                       as total_orders,
        count(*) filter (where o.is_delivered)                         as delivered_orders,
        count(*) filter (where o.is_returned)                          as returned_orders,
        count(*) filter (where o.outcome_group = 'cancelled')          as cancelled_orders,
        count(*) filter (where o.outcome_group = 'in_progress')        as in_progress_orders,
        count(*) filter (where o.is_sla_breach)                        as sla_breach_orders,
        count(*) filter (where o.is_cod)                               as cod_orders,
        sum(o.cod_amount_vnd) filter (where o.is_cod)                  as cod_amount_vnd,
        sum(o.weight_gram)                                             as total_weight_gram,
        avg(o.delivery_hours) filter (where o.is_delivered)            as avg_delivery_hours
    from o
    group by 1, 2
)

select
    agg.date_id,
    d.date_day,
    d.week_start,
    d.year,
    d.quarter,
    d.month,
    d.day_of_week_vn,
    d.is_weekend,
    d.is_holiday_vn,
    agg.region,
    agg.total_orders,
    agg.delivered_orders,
    agg.returned_orders,
    agg.cancelled_orders,
    agg.in_progress_orders,
    agg.sla_breach_orders,
    agg.cod_orders,
    coalesce(agg.cod_amount_vnd, 0)                                    as cod_amount_vnd,
    agg.total_weight_gram,
    -- tỷ lệ (%) — mẫu số là total_orders, làm tròn 2 chữ số
    round(agg.delivered_orders   * 100.0 / nullif(agg.total_orders, 0), 2) as success_rate_pct,
    round(agg.returned_orders    * 100.0 / nullif(agg.total_orders, 0), 2) as return_rate_pct,
    round(agg.sla_breach_orders  * 100.0 / nullif(agg.total_orders, 0), 2) as sla_breach_rate_pct,
    round(agg.avg_delivery_hours, 2)                                   as avg_delivery_hours
from agg
inner join d on agg.date_id = d.date_id
