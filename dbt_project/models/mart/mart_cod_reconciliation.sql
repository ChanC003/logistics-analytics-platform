-- Engine: DuckDB
-- mart_cod_reconciliation — đối soát COD theo tuần × vùng kho thu:
--   tổng phải thu vs đã thu, chênh lệch, tỷ lệ đơn lệch.
with c as (
    select * from {{ ref('fct_cod') }}
),
d as (
    select date_id, week_start, year, quarter from {{ ref('dim_date') }}
)

select
    d.week_start,
    d.year,
    d.quarter,
    coalesce(c.warehouse_region, 'unknown')                      as region,
    count(*)                                                     as cod_records,
    count(*) filter (where c.has_discrepancy)                    as discrepancy_records,
    sum(c.cod_amount_vnd)                                        as total_cod_amount_vnd,
    sum(c.collected_amount_vnd)                                  as total_collected_vnd,
    sum(c.discrepancy_amount_vnd)                                as net_discrepancy_vnd,
    sum(c.abs_discrepancy_vnd)                                   as gross_discrepancy_vnd,
    round(count(*) filter (where c.has_discrepancy) * 100.0 / nullif(count(*), 0), 2) as discrepancy_rate_pct,
    round(sum(c.collected_amount_vnd) * 100.0 / nullif(sum(c.cod_amount_vnd), 0), 2)  as collection_rate_pct
from c
inner join d on c.date_id = d.date_id
group by 1, 2, 3, 4
