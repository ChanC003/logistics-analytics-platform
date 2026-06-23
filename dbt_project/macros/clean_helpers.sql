{#
  Macro dùng chung cho staging/core — chuẩn hoá kiểu & clean dirty data.
  Raw layer CỐ Ý bẩn (xem processing.md Phase 1). Các macro này tập trung logic
  clean ở 1 chỗ để mọi staging model nhất quán.
#}

{# Cast cột DOUBLE (có NaN) sang BIGINT an toàn: NaN/inf → NULL trước khi cast #}
{% macro to_bigint(col) %}
  CASE
    WHEN {{ col }} IS NULL THEN NULL
    WHEN isnan({{ col }}) OR isinf({{ col }}) THEN NULL
    ELSE CAST({{ col }} AS BIGINT)
  END
{% endmacro %}


{# Parse cột dt kiểu VARCHAR ('2024-10-05') sang DATE. TRY_CAST → NULL nếu format hỏng #}
{% macro parse_dt(col) %}
  TRY_CAST({{ col }} AS DATE)
{% endmacro %}


{# TRIM + nullif chuỗi rỗng → NULL (clean text dirty) #}
{% macro clean_text(col) %}
  NULLIF(TRIM({{ col }}), '')
{% endmacro %}


{#
  Chuẩn hoá enum status đơn hàng — clean enum drift CỐ Ý của dirty layer:
  'DONE'/'FINISH'/'Delivered' → 'delivered'. Map các biến thể về canonical lowercase.
#}
{% macro normalize_order_status(col) %}
  CASE
    WHEN lower(trim({{ col }})) IN ('delivered', 'done', 'finish', 'finished', 'success')
      THEN 'delivered'
    WHEN lower(trim({{ col }})) IN ('return_to_sender', 'returned', 'return')
      THEN 'return_to_sender'
    WHEN lower(trim({{ col }})) IN ('cancelled', 'canceled', 'cancel')
      THEN 'cancelled'
    WHEN lower(trim({{ col }})) IN ('ready_to_pick', 'ready', 'waiting_pickup')
      THEN 'ready_to_pick'
    WHEN lower(trim({{ col }})) IN ('picking', 'picked', 'pickup')
      THEN 'picking'
    WHEN lower(trim({{ col }})) IN ('in_transit', 'transit', 'transporting')
      THEN 'in_transit'
    WHEN lower(trim({{ col }})) IN ('delivering', 'delivery', 'shipping')
      THEN 'delivering'
    ELSE lower(trim({{ col }}))
  END
{% endmacro %}


{#
  Nhóm status thành 3 lớp nghiệp vụ cho mart (success/return/in_progress).
  Dùng SAU khi đã normalize_order_status.
#}
{% macro order_outcome_group(status_col) %}
  CASE
    WHEN {{ status_col }} = 'delivered'         THEN 'success'
    WHEN {{ status_col }} = 'return_to_sender'  THEN 'return'
    WHEN {{ status_col }} = 'cancelled'         THEN 'cancelled'
    ELSE 'in_progress'
  END
{% endmacro %}
