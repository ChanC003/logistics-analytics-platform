-- Engine: DuckDB
-- Data-quality WARN: đơn giao thành công nhưng vẫn có failure_reason = mâu thuẫn field.
--   Đây là dirty CỐ Ý (light_issue, ~1.5k đơn) — KHÔNG fail pipeline, chỉ cảnh báo để analyst
--   thấy. severity=warn + error_if ngưỡng cao hơn lượng dirty đã biết (phát hiện nếu tăng bất thường).
{{ config(severity='warn', warn_if='>0', error_if='>5000') }}

select
    order_code,
    status,
    outcome_group,
    failure_reason,
    _data_quality
from {{ ref('fct_shipping_order') }}
where outcome_group = 'success'
  and failure_reason is not null
