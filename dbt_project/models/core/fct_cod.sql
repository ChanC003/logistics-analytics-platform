-- Engine: DuckDB
-- fct_cod — fact đối soát COD (grain: 1 cod_id). Join region kho thu.
with c as (
    select * from {{ ref('stg_cod') }}
),
wh as (select warehouse_id, region from {{ ref('dim_warehouse') }})

select
    c.cod_id,
    c.order_code,
    c.warehouse_id,
    wh.region                                  as warehouse_region,
    c.dt,
    cast(strftime(c.dt, '%Y%m%d') as integer)  as date_id,
    c.cod_amount_vnd,
    c.collected_amount_vnd,
    c.discrepancy_amount_vnd,
    abs(c.discrepancy_amount_vnd)              as abs_discrepancy_vnd,
    c.has_discrepancy,
    c.cod_status,
    c.reconcile_status,
    c.collect_at,
    c._data_quality
from c
left join wh on c.warehouse_id = wh.warehouse_id
