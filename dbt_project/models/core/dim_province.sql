-- Engine: DuckDB
-- dim_province — clean passthrough từ staging
select
    province_id,
    province_name,
    region,
    region_idx
from {{ ref('stg_province') }}
