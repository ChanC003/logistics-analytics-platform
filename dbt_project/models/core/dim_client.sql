-- Engine: DuckDB
-- dim_client — join province/district name; phân nhóm channel từ client_type
with c as (
    select * from {{ ref('stg_client') }}
),
p as (
    select * from {{ ref('stg_province') }}
)

select
    c.client_id,
    c.shop_id,
    c.client_type,
    -- nhóm kênh: sàn TMĐT vs SME/TTS — derive ở core (transform layer)
    case
        when upper(c.client_type) in ('SHOPEE', 'LAZADA', 'TIKI', 'SENDO')
            then 'marketplace'
        when upper(c.client_type) = 'SME' then 'sme'
        when upper(c.client_type) = 'TTS' then 'tts'
        else 'other'
    end                          as client_channel,
    c.province_id,
    p.province_name,
    p.region,
    c.district_id,
    c.is_b2b,
    c.created_date,
    c.tier
from c
left join p on c.province_id = p.province_id
