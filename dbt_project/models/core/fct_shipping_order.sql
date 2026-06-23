-- Engine: DuckDB
-- fct_shipping_order — fact đơn hàng (grain: 1 order_code). Đã dedup ở staging.
--   Thêm region (from dim_warehouse deliver) để mart group theo vùng nhanh.
with o as (
    select * from {{ ref('stg_shippingorder') }}
),
wh as (
    select warehouse_id, region, region_shortname, warehouse_type
    from {{ ref('dim_warehouse') }}
)

select
    o.order_code,
    o.client_id,
    o.shop_id,
    o.date_id,
    o.dt,
    o.created_at,
    -- địa lý theo kho giao
    o.deliver_warehouse_id,
    wh.region                       as deliver_region,
    wh.warehouse_type               as deliver_warehouse_type,
    o.pick_warehouse_id,
    o.return_warehouse_id,
    o.from_district_id,
    o.to_district_id,
    -- nhân sự
    o.pick_user_id,
    o.deliver_user_id,
    o.return_user_id,
    o.deliver_shift,
    -- dịch vụ + kích thước
    o.service_type_id,
    o.service_id,
    o.type_order_code,
    o.weight_gram,
    o.converted_weight_gram,
    -- tiền
    o.cod_amount_vnd,
    o.cod_failed_amount_vnd,
    o.insurance_value_vnd,
    (o.cod_amount_vnd > 0)          as is_cod,
    -- trạng thái + kết quả
    o.status,
    o.outcome_group,
    (o.outcome_group = 'success')   as is_delivered,
    (o.outcome_group = 'return')    as is_returned,
    o.is_sla_breach,
    o.failure_reason,
    o.is_b2b,
    -- thời gian giao
    o.end_pick_at,
    o.first_delivered_at,
    o.end_delivery_at,
    o.delivery_hours,
    o._data_quality
from o
left join wh on o.deliver_warehouse_id = wh.warehouse_id
