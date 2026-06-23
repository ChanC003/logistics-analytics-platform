-- Engine: DuckDB
-- Singular test: discrepancy_amount = SHORTFALL = cod_amount - collected (số dương khi thu thiếu).
--   Đây là định nghĩa của generator (đối soát: còn thiếu bao nhiêu so với phải thu).
--   LOẠI cod_status='adjustment': đây là bản ghi điều chỉnh (discrepancy=0 cố ý), không phải
--   sự kiện thu tiền → công thức cod-collected không áp dụng.
-- Cho phép lệch ±1 VND do làm tròn DOUBLE→BIGINT ở staging. Trả row VI PHẠM → fail.
select
    cod_id,
    cod_status,
    cod_amount_vnd,
    collected_amount_vnd,
    discrepancy_amount_vnd,
    (cod_amount_vnd - collected_amount_vnd) as expected_discrepancy
from {{ ref('fct_cod') }}
where cod_status != 'adjustment'
  and abs(discrepancy_amount_vnd - (cod_amount_vnd - collected_amount_vnd)) > 1
