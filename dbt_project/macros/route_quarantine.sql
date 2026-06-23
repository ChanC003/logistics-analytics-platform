{#
  route_quarantine — trả về mệnh đề WHERE để LOẠI BỎ row heavy_issue khỏi luồng chính.
  Dùng trong staging model có cột _data_quality. heavy_issue được giữ riêng qua
  model stg_*_quarantine (nếu cần audit) — luồng chính chỉ giữ clean + light_issue.

  Cách dùng:
    SELECT ... FROM {{ source('raw','data_cod') }}
    WHERE {{ keep_non_quarantine('_data_quality') }}
#}
{% macro keep_non_quarantine(quality_col='_data_quality') %}
  ( {{ quality_col }} IS NULL OR {{ quality_col }} != '{{ var("quarantine_quality_flag") }}' )
{% endmacro %}


{# Ngược lại — chỉ lấy row bị quarantine (heavy_issue) để audit #}
{% macro only_quarantine(quality_col='_data_quality') %}
  ( {{ quality_col }} = '{{ var("quarantine_quality_flag") }}' )
{% endmacro %}
