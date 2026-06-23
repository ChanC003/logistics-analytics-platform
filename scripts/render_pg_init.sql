-- PostgreSQL init script for Render demo
-- Run after creating the database on Render
-- Data loaded separately via \copy or psql COPY

CREATE TABLE IF NOT EXISTS mart_daily_kpi (
    date_id             INTEGER,
    date_day            DATE,
    week_start          DATE,
    year                INTEGER,
    quarter             INTEGER,
    month               INTEGER,
    day_of_week_vn      TEXT,
    is_weekend          BOOLEAN,
    is_holiday_vn       BOOLEAN,
    region              TEXT,
    total_orders        BIGINT,
    delivered_orders    BIGINT,
    returned_orders     BIGINT,
    cancelled_orders    BIGINT,
    in_progress_orders  BIGINT,
    sla_breach_orders   BIGINT,
    cod_orders          BIGINT,
    cod_amount_vnd      BIGINT,
    total_weight_gram   BIGINT,
    success_rate_pct    DOUBLE PRECISION,
    return_rate_pct     DOUBLE PRECISION,
    sla_breach_rate_pct DOUBLE PRECISION,
    avg_delivery_hours  DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS mart_hub_performance (
    warehouse_id        BIGINT,
    warehouse_name      TEXT,
    warehouse_type      TEXT,
    region              TEXT,
    region_shortname    TEXT,
    province_name       TEXT,
    total_orders        BIGINT,
    delivered_orders    BIGINT,
    returned_orders     BIGINT,
    sla_breach_orders   BIGINT,
    active_shippers     BIGINT,
    cod_amount_vnd      BIGINT,
    success_rate_pct    DOUBLE PRECISION,
    return_rate_pct     DOUBLE PRECISION,
    sla_breach_rate_pct DOUBLE PRECISION,
    avg_delivery_hours  DOUBLE PRECISION,
    orders_per_shipper  DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS mart_sla_breakdown (
    week_start          DATE,
    year                INTEGER,
    quarter             INTEGER,
    region              TEXT,
    service_code        TEXT,
    delivered_orders    BIGINT,
    sla_breach_orders   BIGINT,
    sla_breach_rate_pct DOUBLE PRECISION,
    avg_delivery_hours  DOUBLE PRECISION,
    p50_delivery_hours  DOUBLE PRECISION,
    p90_delivery_hours  DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS mart_failure_reasons (
    region                  TEXT,
    failure_reason          TEXT,
    failed_attempts         BIGINT,
    affected_orders         BIGINT,
    pct_of_region_failures  DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS mart_cod_reconciliation (
    week_start             DATE,
    year                   INTEGER,
    quarter                INTEGER,
    region                 TEXT,
    cod_records            BIGINT,
    discrepancy_records    BIGINT,
    total_cod_amount_vnd   BIGINT,
    total_collected_vnd    BIGINT,
    net_discrepancy_vnd    BIGINT,
    gross_discrepancy_vnd  BIGINT,
    discrepancy_rate_pct   DOUBLE PRECISION,
    collection_rate_pct    DOUBLE PRECISION
);
