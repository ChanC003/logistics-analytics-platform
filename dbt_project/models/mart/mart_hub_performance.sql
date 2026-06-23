-- Engine: DuckDB
-- mart_hub_performance — hiệu suất từng kho giao (KTC/BC):
--   sản lượng, success/return rate, SLA, leadtime — để rank kho.
with o as (
    select * from {{ ref('fct_shipping_order') }}
    where deliver_warehouse_id is not null
),
w as (
    select warehouse_id, warehouse_name, warehouse_type, region, region_shortname, province_name
    from {{ ref('dim_warehouse') }}
),
agg as (
    select
        o.deliver_warehouse_id                                   as warehouse_id,
        count(*)                                                 as total_orders,
        count(*) filter (where o.is_delivered)                   as delivered_orders,
        count(*) filter (where o.is_returned)                    as returned_orders,
        count(*) filter (where o.is_sla_breach)                  as sla_breach_orders,
        count(distinct o.deliver_user_id)                        as active_shippers,
        avg(o.delivery_hours) filter (where o.is_delivered)      as avg_delivery_hours,
        sum(o.cod_amount_vnd) filter (where o.is_cod)            as cod_amount_vnd
    from o
    group by 1
)

select
    w.warehouse_id,
    w.warehouse_name,
    w.warehouse_type,
    w.region,
    w.region_shortname,
    w.province_name,
    agg.total_orders,
    agg.delivered_orders,
    agg.returned_orders,
    agg.sla_breach_orders,
    agg.active_shippers,
    coalesce(agg.cod_amount_vnd, 0)                              as cod_amount_vnd,
    round(agg.delivered_orders  * 100.0 / nullif(agg.total_orders, 0), 2) as success_rate_pct,
    round(agg.returned_orders   * 100.0 / nullif(agg.total_orders, 0), 2) as return_rate_pct,
    round(agg.sla_breach_orders * 100.0 / nullif(agg.total_orders, 0), 2) as sla_breach_rate_pct,
    round(agg.avg_delivery_hours, 2)                             as avg_delivery_hours,
    -- năng suất: đơn / shipper
    round(agg.total_orders * 1.0 / nullif(agg.active_shippers, 0), 1)     as orders_per_shipper
from agg
inner join w on agg.warehouse_id = w.warehouse_id
