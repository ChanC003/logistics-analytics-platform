-- Engine: DuckDB
-- snap_client_tier — SCD Type 2 theo dõi thay đổi tier/channel của client theo thời gian.
--   Use case: client nâng hạng Bronze→Gold→Diamond, đổi kênh — cần lịch sử để phân tích cohort.
--   Chạy lại mỗi ngày (Airflow Phase 3): dbt phát hiện thay đổi tier → thêm version mới.
{% snapshot snap_client_tier %}

{{
    config(
        target_schema='snapshot',
        unique_key='client_id',
        strategy='check',
        check_cols=['tier', 'client_channel', 'is_b2b']
    )
}}

select
    client_id,
    shop_id,
    client_type,
    client_channel,
    tier,
    is_b2b,
    region,
    province_name
from {{ ref('dim_client') }}

{% endsnapshot %}
