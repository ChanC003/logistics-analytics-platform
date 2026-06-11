# 02 — Logistics Analytics Platform

Operational analytics system mô phỏng mạng lưới 3PL tại Việt Nam — tracking SLA breach, hub performance, delivery success rate, và COD reconciliation. Stack chạy local trên DuckDB, orchestrate bằng Airflow, visualize bằng Metabase.

---

## 1. Mục đích

- Demo end-to-end data platform: ingest → transform → serve
- Xử lý **56M+ rows** (5M orders + 40M package events + 11M+ rows còn lại) trên DuckDB để chứng minh hiểu columnar analytics
- Dashboard mở được trực tiếp trên trình duyệt (không cần Power BI)
- **Yêu cầu:** RAM >= 16GB để chạy dbt full-refresh trên 40M inside_history

## 2. Data — Tự sinh 100%

Synthetic dataset modeled on Vietnamese 3PL operations:

| Bảng | Volume | Mô tả |
|---|---|---|
| `dim_warehouse` | ~2,000 | Kho trung chuyển (KTC) và bưu cục (BC) |
| `dim_province` | 63 | Tỉnh thành VN |
| `dim_district` | ~700 | Quận/huyện |
| `dim_client` | 50k | Shop/đối tác gửi hàng (TTS/SME/SHOPEE) |
| `dim_shipper` | 1.5k | Tài xế giao hàng |
| `dim_date` | 730 | 2 năm 2024–2025 |
| `data_shippingorder_now` | 5M | Đơn hàng 2024–2025 |
| `data_inside_history` | 40M | Package action events tại từng kho |
| `data_transportation` | 500k | Chuyến xe tải liên kho (truck trips) |
| `data_shipment` | 7.5M | Chuyến giao last-mile đến khách |
| `data_cod` | 3M | Đối soát COD theo shipper/ngày |

**Realistic patterns:** seasonality (peak 11–12), day-of-week, geographic skew (HCM+HN = 60%), SLA breach 5–12%, failure reason mix.

> Generator code: [src/generators/](src/generators/) — chạy reproducible bằng seed cố định.

## 3. Architecture

```
Synthetic Generator (Python)
        ↓
   data/raw/*.parquet
        ↓
       DuckDB
        ↓
   dbt Models (staging → core → mart)
        ↓
   Airflow Orchestrate (daily DAG)
        ↓
   Metabase Dashboard
```

Chi tiết: [docs/architecture.md](docs/architecture.md) · Data model: [docs/data-model.md](docs/data-model.md)

## 4. Tech Stack

| Layer | Tech |
|---|---|
| Generation | Python, Faker, numpy, pandas |
| Storage | DuckDB (file-based, columnar) |
| Transform | dbt-duckdb |
| Orchestration | Apache Airflow (Docker) |
| Serving | Metabase (self-hosted, Docker) |
| Container | Docker, docker-compose |
| Testing | pytest, dbt tests, Great Expectations |

### Vì sao chọn DuckDB?

- **Performance:** 10–50x nhanh hơn Postgres/MySQL cho analytical query (GROUP BY, aggregation, window) trên 5M+ rows — columnar storage + vectorized execution
- **Zero-setup demo:** warehouse là 1 file `.duckdb` duy nhất — recruiter clone repo, chạy `dbt run` là xem được, không cần dựng server
- **Modern stack signal:** `dbt-duckdb` là combo được cộng đồng dbt highlight 2024–2026 cho local analytics — cho thấy nắm xu hướng tooling hiện đại
- **Khác biệt với project 01:** project [01-Banking-Pipeline](../01-Banking-Pipeline/) đã dùng Postgres (OLTP) + Snowflake (warehouse) → project này dùng DuckDB để show "lakehouse local" pattern, hai project bổ sung nhau

**Trade-off chấp nhận được cho mục đích demo:** single-writer (Airflow chạy tuần tự, không bị ảnh hưởng), không HA/replication (đây là portfolio, không phải prod), không distributed (5M rows fit RAM thoải mái).

## 5. Quick Start

```powershell
# 1. Setup env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Generate synthetic data (~5 phút, output ra data/raw/)
python src/generators/generate_all.py --seed 42 --years 2

# 3. Build dbt models vào DuckDB
cd dbt_project
dbt run
dbt test

# 4. Khởi động Airflow + Metabase
docker-compose up -d

# 5. Mở Metabase
# http://localhost:3000 — connect tới DuckDB warehouse.duckdb
```

Full setup + docker stack: [docs/setup.md](docs/setup.md)

## 6. Roadmap (5 phase, ~11 ngày)

- [ ] **Phase 1** — Data generation (Python script + sample 50k row commit-able)
- [ ] **Phase 2** — DuckDB + dbt models (staging → core → mart)
- [ ] **Phase 3** — Airflow DAG (daily extract → transform → publish)
- [ ] **Phase 4** — Metabase setup (self-hosted Docker, connect DuckDB, build dashboards)
- [ ] **Phase 5** — Docker compose full stack + README + screenshot demo

Theo dõi tiến độ: [processing.md](processing.md)

## 7. Cấu trúc folder

```
02-Logistics-Analytics-Platform/
├── README.md
├── processing.md
├── requirements.txt
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── setup.md
│   └── screenshots/
├── src/
│   ├── generators/        ← Sinh synthetic data
│   └── extract/           ← (Optional) connector mock
├── sql/
│   ├── staging/
│   ├── core/
│   └── mart/
├── dbt_project/           ← dbt-duckdb project
├── notebooks/             ← Khám phá dữ liệu
├── data/
│   ├── raw/              ← .parquet (gitignored, regenerate được)
│   └── sample/           ← 50k rows commit-able
├── airflow/
│   └── dags/
├── metabase/              ← Metabase config, dashboard exports
│   └── dashboards/        ← Dashboard JSON exports (version control)
├── docker/
│   └── docker-compose.yml ← Airflow + Metabase + DuckDB volume
└── tests/
```

## 8. Thay đổi so với spec gốc

| Spec gốc | Thực tế | Lý do |
|---|---|---|
| Power BI | Metabase (self-hosted Docker) | Open-source, không cần license, kết nối DuckDB native |
| HTML dashboard tĩnh | Metabase | BI tool thực tế hơn cho portfolio — recruiter thấy real BI workflow |
| ERP/WMS API | Synthetic generator | Không có API thật, tự sinh control 100% |

Metabase dashboard JSON exports sẽ lưu vào `metabase/dashboards/`.
