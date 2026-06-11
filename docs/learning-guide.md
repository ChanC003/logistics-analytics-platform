# Hướng dẫn thực hành — Cầm tay chỉ việc từng câu lệnh
## Project: Logistics Analytics Platform (GHN-style 3PL)

> Tài liệu này dẫn bạn qua **toàn bộ vòng đời** của một data project thực tế —
> từ lúc nhận bài toán chưa rõ ràng cho đến lúc báo cáo kết quả cho stakeholder.
>
> Khác với một guide lý thuyết, ở đây **mỗi bước có câu lệnh chính xác để copy-paste**,
> **kết quả bạn phải nhìn thấy**, và **nếu lỗi thì sửa thế nào**. Mọi lệnh đã được
> viết khớp với code thật trong repo này (tên file, tên cột, flag CLI).

### Cách đọc tài liệu này

Mỗi câu lệnh đi kèm 3 thứ:

```
$ <câu lệnh để gõ>            ← copy nguyên dòng này
→ <kết quả mong đợi>          ← bạn PHẢI thấy thứ tương tự, nếu không là sai
⚠ <lỗi thường gặp + cách fix> ← khi output không như mong đợi
```

**Ký hiệu môi trường:**
- `PS>` = PowerShell (terminal mặc định trên Windows của project này)
- Mọi đường dẫn gốc: `f:\ChangPH-project\02-Logistics-Analytics-Platform`
- Trạng thái hiện tại của project: **Phase 1 generator đã xong (smoke test passed)**. Phase 2–5 (dbt / Airflow / Metabase) **chưa build** — các lệnh ở những phase đó đánh dấu `[CHƯA BUILD]` và là lệnh bạn *sẽ* chạy sau khi tạo file tương ứng.

---

## Tổng quan: Bạn đang đóng vai gì?

Bạn là **Data Engineer junior** vừa vào team tại một công ty logistics (mô phỏng GHN).
Manager giao cho bạn:

> *"Chúng ta cần một analytics platform cho mạng lưới vận hành —
> tracking hiệu suất kho, tỷ lệ giao thành công, SLA, và đối soát COD.
> Em tự thiết kế và build đi."*

Đó là tất cả. Không có spec. Không có data sẵn. Không có deadline cụ thể.

**Mục tiêu cuối cùng:** Một pipeline chạy được từ đầu đến cuối —
data → transform → dashboard — và bạn giải thích được từng quyết định.

**Pipeline cuối cùng trông như thế nào:**

```
Python generators          DuckDB              dbt              Metabase
(src/generators/*)   →   warehouse.duckdb  →  staging/core/  →  4 dashboard
56M+ rows synthetic       (data/)             mart/             localhost:3000
        ▲                                       ▲
        └──────────── Airflow DAG orchestrate mỗi 6h sáng ──────┘
```

---

# PHASE 0 — NHẬN BÀI TOÁN & HÌNH DUNG

> Phase này **không gõ lệnh build gì cả**. Bạn chỉ đọc, ghi chú, và khảo sát data.
> Đây là phase junior hay bỏ qua nhất — và trả giá đắt nhất.

### Checklist đầu vào Phase 0

```
□ Đã nhận yêu cầu từ stakeholder (dù chỉ 1 câu mơ hồ)
□ Có quyền truy cập ít nhất 1 nguồn data (thật hoặc mô phỏng)
□ Có môi trường: laptop + terminal (PowerShell) + text editor (VS Code)
```

---

### Bước 0.1 — Đọc bài toán, viết lại bằng ngôn ngữ của mình

**Việc phải làm:** Đừng mở terminal. Mở một file markdown, viết lại yêu cầu bằng câu của bạn.

**Câu lệnh tạo file ghi chú:**
```
PS> code docs\my-understanding.md     # mở file mới trong VS Code
```
→ VS Code mở một tab trống tên `my-understanding.md`.

**Trong file đó, trả lời 5 câu hỏi (gõ trực tiếp):**
```
□ Stakeholder muốn BIẾT điều gì? (không phải muốn LÀM gì)
□ Ai dùng output? (Manager? Ops team? C-level? Finance?)
□ Họ dùng nó để ra quyết định gì?
□ "Analytics platform" với họ là gì — dashboard? report? alert?
□ Data ở đâu, format gì, ai sở hữu?
```

**Ví dụ một câu trả lời tốt (paste vào file rồi sửa):**
> "Ops team cần xem mỗi sáng: hôm qua bao nhiêu đơn giao thành công,
> KTC nào đang chậm, shipper nào có COD chưa đối soát.
> Họ nhìn số, không cần drill-down phức tạp.
> Data từ hệ thống vận hành — không có API, phải tự sinh."

**Sai lầm phổ biến:** Nghe xong là cài thư viện. Chưa biết output là gì đã viết code.

---

### Bước 0.2 — Khảo sát dữ liệu thực tế (Discovery)

**Việc phải làm:** Trước khi thiết kế, hỏi *"Data thực tế trông như thế nào?"*

Trong project này, nguồn discovery là OpenMetadata catalog GHN (21,336 tables) và
file mẫu nếu có. Đây là bước **đọc để hiểu**, không phải build.

> ⚠ **QUY ƯỚC BẮT BUỘC của project:** mọi file CSV/Parquet/Excel **phải** đọc qua
> `analyst` sub-agent, KHÔNG đọc trực tiếp (dataset 5M+ rows làm overflow context).
> Xem [`file-analysis.md`](C:/Users/ADMIN/.claude/rules/file-analysis.md).

**Nếu bạn tự khảo sát một file mẫu nhỏ bằng Python (chỉ khi < vài nghìn rows):**
```python
# Chạy trong Python REPL hoặc 1 cell notebook — KHÔNG dùng cho file 5M rows
import pandas as pd
df = pd.read_csv("data/raw/sample.csv", nrows=1000)
print(df.dtypes)          # → kiểu từng cột
print(df.isnull().sum())  # → số NULL mỗi cột
print(df.describe())      # → min/max/mean của cột số
print(df.head(5))         # → 5 dòng đầu
```

**5 câu hỏi Discovery phải trả lời:**
```
□ Có những entity nào? (đơn hàng, kho, shipper, tỉnh, client...)
□ Mỗi entity lưu ở bảng nào? Tên cột thật là gì?
□ Data có dirty không? Bao nhiêu NULL? Có duplicate không?
□ Volume thực tế bao nhiêu rows?
□ Có pattern đặc biệt? (seasonality, skew theo địa lý...)
```

**Output bước này:** ghi notes thô. Trong repo này đã thành [`docs/entity-map.md`](entity-map.md).

**Bài học discovery THẬT của project này (ghi để bạn không lặp lại sai):**
- GHN lưu `weight` bằng **gram** (không phải kg)
- Địa lý phân cấp `province → district → ward` (không chỉ tỉnh)
- Một đơn có **4 warehouse roles**: `pick / deliver / current / return`
- GHN dùng `client_id` / `shop_id`, **không** có khái niệm "customer"
- Kho gọi là `warehouse`, phân loại `KTC` (kho trung chuyển) vs `BC` (bưu cục)

Không discovery → thiết kế sai từ đầu → làm lại cả tuần.

---

### Bước 0.3 — Lên ý tưởng kiến trúc (vẽ 2–3 phương án)

**Việc phải làm:** Vẽ text diagram từ data → output. Ít nhất 2 phương án.

```
Phương án A — Đơn giản nhất:
  CSV → Python → SQLite → Jupyter notebook

Phương án B — Thực tế (CHỌN cái này):
  Generator → Parquet → DuckDB → dbt → Metabase   (+ Airflow orchestrate)

Phương án C — Overkill cho scope này:
  Kafka → Spark → Snowflake → Looker
```

**5 câu hỏi để chốt phương án:**
```
□ Scale bao nhiêu rows? (56M → cần columnar → không SQLite)
□ Stakeholder tự xem được không? (Metabase > Jupyter notebook)
□ Cần chạy lại hàng ngày? (có → cần orchestration → Airflow)
□ Team biết tool đó không? (học việc → chọn tool phổ biến, docs tốt)
□ Demo được không cần cài thêm? (DuckDB file-based > PostgreSQL server)
```

**Quyết định THẬT của project + lý do (đã ghi trong [`processing.md`](../processing.md)):**

| Quyết định | Lý do cụ thể |
|---|---|
| DuckDB thay PostgreSQL | File-based — recruiter clone repo xem được ngay, không dựng server |
| Metabase thay HTML tự viết | BI tool thật — recruiter thấy real workflow |
| Parquet thay CSV | Columnar — 56M rows query nhanh hơn 10–50× |
| dbt thay raw SQL | Lineage + test + docs — chuẩn industry |

**Output:** [`docs/architecture.md`](architecture.md) (đã có).

---

### Bước 0.4 — Xác định scope & hỏi stakeholder

Trước khi build, confirm những điểm mơ hồ. Template gửi manager:

```
Hi [Manager],
Em đã review yêu cầu, cần xác nhận trước khi bắt đầu:
1. METRIC: "hiệu suất KTC" = throughput (đơn/ngày) + SLA breach rate. Đúng không?
2. GRANULARITY: Dashboard xem theo ngày hay theo tuần?
3. DATA: Chưa có data thật — em sinh synthetic mô phỏng GHN. OK chứ?
4. DEADLINE: Ưu tiên pipeline chạy được hay dashboard đẹp trước?
Thanks, [Tên]
```

**Lý do:** Junior sợ hỏi nên tự đoán. Đoán sai = 1–2 ngày làm lại. Hỏi sớm rẻ hơn.

### ⛔ GATE Phase 0 → Phase 1 (phải đạt TẤT CẢ)

```
□ Viết được 3–5 câu mô tả bài toán bằng lời mình (không copy đề)
□ Có entity map thô: ≥ 5 entity trong domain
□ Chọn 1 kiến trúc với ≥ 2 lý do cụ thể (không phải "tôi thích tool này")
□ Đã gửi câu hỏi xác nhận (hoặc tự trả lời nếu solo)
□ docs/architecture.md tồn tại (dù draft)
```

---

# PHASE 1 — DATA GENERATION (BUILD GENERATORS)

> Đây là phase **đang ở** của project. Code generator đã viết xong, smoke test passed.
> Phần dưới là **chính xác các lệnh** để chạy lại từ đầu trên máy mới.

### Checklist đầu vào Phase 1

```
□ docs/data-model.md + data-quality-strategy.md đã xong (Phase gate trước)
□ Python 3.11+ đã cài  (kiểm tra: python --version)
□ Đang đứng ở thư mục project: f:\ChangPH-project\02-Logistics-Analytics-Platform
```

---

### Bước 1.1 — Setup môi trường (LÀM TRƯỚC mọi thứ)

**1. Kiểm tra Python:**
```
PS> python --version
```
→ `Python 3.11.x` hoặc `3.12.x`.
⚠ Nếu `python` không nhận → cài Python từ python.org, tick "Add to PATH", mở lại terminal.

**2. Vào đúng thư mục project:**
```
PS> cd f:\ChangPH-project\02-Logistics-Analytics-Platform
```
→ Prompt đổi thành `...\02-Logistics-Analytics-Platform>`.

**3. Tạo virtual environment** (chỉ làm 1 lần):
```
PS> python -m venv .venv
```
→ Sinh ra thư mục `.venv\` trong project. Không in gì ra là bình thường.
⚠ Nếu báo `venv` lỗi → `python -m pip install --upgrade pip` rồi thử lại.

**4. Kích hoạt venv** (làm MỖI LẦN mở terminal mới):
```
PS> .\.venv\Scripts\Activate.ps1
```
→ Prompt có tiền tố `(.venv)` ở đầu. Đó là dấu hiệu venv đang bật.
⚠ Nếu báo *"running scripts is disabled"* → chạy 1 lần:
```
PS> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
rồi `Activate.ps1` lại.

**5. Cài dependencies** (đã pin version sẵn trong `requirements.txt`):
```
PS> pip install --timeout 120 -r requirements.txt
```
→ Cài pandas 2.2.3, numpy 1.26.4, faker, duckdb 1.1.3, dbt-duckdb, great-expectations, airflow, pytest, pyarrow.
⚠ Nếu **network timeout** khi tải Faker (~1.8MB) → tăng timeout hoặc cài lại từng cái:
```
PS> pip install --timeout 300 pandas numpy faker pyarrow
PS> pip install --timeout 300 duckdb dbt-duckdb great-expectations pytest
```

**6. Verify cài đúng:**
```
PS> python -c "import duckdb, pandas, numpy, faker; print('OK', duckdb.__version__)"
```
→ `OK 1.1.3`
⚠ `ModuleNotFoundError` → venv chưa bật (xem lại bước 4) hoặc pip cài vào Python khác.

**Tại sao setup trước?** Nhiều junior viết 200 dòng mới phát hiện thư viện không tương thích. Setup → verify → rồi mới build.

---

### Bước 1.2 — Hiểu cấu trúc generator (đọc trước khi chạy)

**Mỗi generator là 1 file độc lập** trong [`src/generators/`](../src/generators/), có 2 hàm public:
```python
def generate(seed: int, **kwargs) -> pd.DataFrame: ...   # sinh data
def write(df: pd.DataFrame, path: Path) -> None: ...      # ghi .parquet
```

**Thứ tự dependency** (dim đơn giản → dim có FK → fact). Đây là thứ tự `generate_all.py` chạy:
```
1. dim_province           (63 tỉnh hardcode — không FK)
2. dim_district           (FK → province, ~711 rows)
3. dim_date               (730 ngày 2024–2025 — không FK)
4. dim_warehouse          (8 KTC hardcode + 1,992 BC, FK → district)
5. dim_client             (50k client, FK → district)
6. dim_shipper            (1,500 shipper, FK → warehouse)
7. data_shippingorder_now (5M orders — FK tất cả dim)        ← FACT chính
8. data_inside_history    (~40M package events)
9. data_transportation    (~500k truck trips)
10. data_shipment         (~7.5M lastmile trips)
11. data_cod              (~3M COD records)
```
> Lý do thứ tự: fact có FK trỏ vào dim → dim phải tồn tại trước.

**Đọc 1 generator để hiểu pattern** (ví dụ dim đơn giản nhất):
```
PS> code src\generators\dim_province.py
```
→ Bạn thấy: list 63 tỉnh hardcode, `generate()` trả DataFrame, `write()` ghi parquet.

---

### Bước 1.3 — Smoke test (LUÔN chạy cái này TRƯỚC khi generate full)

**Việc:** chạy với data nhỏ để bắt lỗi nhanh (vài giây), không phải chờ 5M rows.

**1. Vào thư mục generators** (bắt buộc — path `data/raw/` là relative):
```
PS> cd src\generators
```

**2. Bật UTF-8 cho terminal** (Windows mặc định CP1252 sẽ vỡ tiếng Việt):
```
PS> $env:PYTHONUTF8=1
```
→ Không in gì. Biến môi trường được set cho session này.
⚠ Nếu quên bước này → `UnicodeEncodeError: 'charmap' codec can't encode...` khi in tên kho tiếng Việt.

**3. Chạy smoke test:**
```
PS> python _test_smoke.py
```
→ In ra row count từng bảng nhỏ + phân bố `_data_quality`. Chạy xong trong vài giây, không lỗi.
⚠ Nếu lỗi → đọc dòng cuối stack trace (file + số dòng), sửa đúng chỗ đó. **Đừng** chạy full khi smoke còn lỗi.

**4. Hoặc dùng `generate_all.py --sample`** (sinh 10k orders, ghi parquet thật để test load):
```
PS> python generate_all.py --sample
```
→ Bảng tổng kết, mỗi dòng dạng:
```
  [  0.1s] dim_province                          63 rows  →  dim_province.parquet
  [  0.3s] dim_district                         711 rows  →  dim_district.parquet
  ...
  [  2.5s] data_shippingorder_now            10,000 rows  →  data_shippingorder_now.parquet
  ...
  Done in XXs  |  11 tables generated
```
> `--sample` patch `N_ORDERS = 10_000` runtime, nên fact chỉ 10k thay vì 5M.

---

### Bước 1.4 — Generate full dataset (5M orders, ~56M rows)

> ⚠ **Yêu cầu máy:** RAM ≥ 16GB (load 40M `inside_history` rows), disk ≥ 10GB cho parquet.
> Chạy ~vài phút đến vài chục phút tùy máy.

**1. Vẫn ở `src/generators/`, venv bật, UTF-8 bật. Chạy:**
```
PS> python generate_all.py --seed 42
```
→ Cùng bảng như trên nhưng số rows thật (fact = 5,000,000). Dòng cuối:
```
  Writing sample 50k rows …
  Sample → ...\data\sample\data_shippingorder_sample.parquet
  Done in XXXs  |  11 tables generated
  Total rows: 56,XXX,XXX
```
> `generate_all.py` tự ghi sample 50k vào `data/sample/` (file này được commit vào git — `data/raw/*.parquet` thì KHÔNG).

**2. Các flag hữu ích của `generate_all.py`** (đọc từ docstring thật của file):
```
PS> python generate_all.py --seed 99      # đổi seed
PS> python generate_all.py --only dim     # CHỈ chạy generator có "dim" trong tên
PS> python generate_all.py --skip cod     # BỎ QUA generator có "cod" trong tên
```
> `--only` / `--skip` so khớp **substring** tên generator, không phải tên chính xác.
> KHÔNG có flag `--rows` — muốn đổi số order, dùng `--sample` (10k) hoặc sửa `N_ORDERS` trong [`config.py`](../src/generators/config.py).

⚠ Nếu treo / hết RAM giữa chừng → kill process Python cũ trước khi chạy lại:
```
PS> Stop-Process -Name python -Force
```

---

### Bước 1.5 — Verify output (BẮT BUỘC trước khi sang Phase 2)

**1. Kiểm tra file parquet đã sinh:**
```
PS> dir ..\..\data\raw\*.parquet
```
→ Liệt kê 11 file: `dim_province.parquet` … `data_cod.parquet`.

**2. Verify schema + dirty distribution của fact chính** (chạy Python inline):
```
PS> python -c "import pandas as pd; df=pd.read_parquet('../../data/raw/data_shippingorder_now.parquet'); print(df.dtypes); print(df['_data_quality'].value_counts()); print(df['status'].value_counts())"
```
→ Bạn phải thấy:
- `_data_quality` có 3 giá trị: `clean` (đa số), `light_issue`, `heavy_issue`
- `status` có các giá trị: `delivered` (~72%), `return_to_sender`, `cancelled`, `ready_to_pick`, `picking`, `in_transit`, `delivering`
- `weight` là kiểu int (gram), `created_date` là datetime, `dt` là date

**3. Verify reproducibility** (cùng seed → cùng output):
```
PS> python generate_all.py --seed 42      # chạy lần 2
```
→ Row count + thời điểm dirty **giống hệt** lần 1. Đây là tính chất phải có của data synthetic tốt.
> Lý do reproducible: mỗi generator set seed cố định (`np.random.default_rng(seed)`, Faker `seed_instance`).

**4. Spot-check một dirty rule cụ thể** — ví dụ ~0.8% weight = 0:
```
PS> python -c "import pandas as pd; df=pd.read_parquet('../../data/raw/data_shippingorder_now.parquet'); print('weight=0:', (df['weight']==0).sum(), 'of', len(df))"
```
→ Số rows weight=0 ≈ 0.8% tổng (theo `docs/data-quality-strategy.md`).

### ⛔ GATE Phase 1 → Phase 2 (phải đạt TẤT CẢ)

```
GENERATOR
□ python generate_all.py --sample chạy không lỗi
□ python generate_all.py --seed 42 sinh đủ 11 parquet, total ~56M rows
□ Chạy 2 lần cùng seed → row count + dirty distribution giống hệt
□ _data_quality có đủ 3 nhóm: clean / light_issue / heavy_issue
□ status đúng enum (delivered/return_to_sender/cancelled/...); KHÔNG có cột phanloaivung
   (phân loại vùng là việc của Analyst layer dbt, đã xóa khỏi generator)
□ data/sample/data_shippingorder_sample.parquet tồn tại (file commit vào git)
```

---

# PHASE 2 — DuckDB + dbt (TRANSFORM)

> `[CHƯA BUILD]` — Phase này sẽ tạo: `load_to_duckdb.py`, `dbt_project/` (config + models).
> Các lệnh dưới là lệnh bạn **sẽ chạy sau khi tạo file**, viết đúng convention dự án.

### Checklist đầu vào Phase 2

```
□ Phase 1 gate pass — 11 parquet trong data/raw/
□ venv bật, dbt-duckdb đã cài (kiểm tra: dbt --version)
□ Đang ở thư mục project root
```

**Kiểm tra dbt cài đúng:**
```
PS> dbt --version
```
→ `Core: 1.8.x` + `duckdb: 1.8.x`.

---

### Bước 2.1 — Load Parquet vào DuckDB `[CHƯA BUILD: src/load_to_duckdb.py]`

**Việc:** đọc 11 file parquet → tạo schema `raw` trong `data/warehouse.duckdb`.

**Khung file sẽ viết** (`src/load_to_duckdb.py`):
```python
# src/load_to_duckdb.py
import duckdb
from pathlib import Path

RAW = Path(__file__).parent.parent / "data" / "raw"
DB  = Path(__file__).parent.parent / "data" / "warehouse.duckdb"

def load_all():
    con = duckdb.connect(str(DB))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    for pq in sorted(RAW.glob("*.parquet")):
        table = pq.stem  # dim_province, data_shippingorder_now, ...
        con.execute(f"""
            CREATE OR REPLACE TABLE raw.{table} AS
            SELECT * FROM read_parquet('{pq.as_posix()}')
        """)
        n = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        print(f"  loaded raw.{table}: {n:,} rows")
    con.close()

if __name__ == "__main__":
    load_all()
```

**Lệnh chạy:**
```
PS> python src\load_to_duckdb.py
```
→ `loaded raw.dim_province: 63 rows` … `loaded raw.data_shippingorder_now: 5,000,000 rows`.

**Verify load bằng DuckDB CLI** (query trực tiếp file db):
```
PS> python -c "import duckdb; con=duckdb.connect('data/warehouse.duckdb'); print(con.execute('SELECT COUNT(*) FROM raw.data_shippingorder_now').fetchone()); print(con.execute('DESCRIBE raw.data_shippingorder_now').df()[['column_name','column_type']].head(20))"
```
→ Row count khớp parquet; `created_date` kiểu `TIMESTAMP`, `dt` kiểu `DATE`, `weight` kiểu `BIGINT`.

**4 câu hỏi tự kiểm ở bước này:**
```
□ Row count trong DuckDB == row count parquet? (không bị truncate)
□ DATE columns đúng kiểu DATE/TIMESTAMP (không phải VARCHAR)?
□ NULL được preserve (không thành chuỗi "None")?
□ dt là DATE, date_id là INT?
```
⚠ Nếu DuckDB báo `Could not set lock on file` → có process khác (Metabase/Airflow) đang mở db. Đóng nó, hoặc connect `read_only=True` cho reader.

---

### Bước 2.2 — Khởi tạo dbt project `[CHƯA BUILD: dbt_project/]`

> Theo [`project-scaffold.md`](C:/Users/ADMIN/.claude/rules/project-scaffold.md): dùng `dbt init`, **không** dựng `models/` rời tay.

**1. Khởi tạo:**
```
PS> cd dbt_project
PS> dbt init logistics
```
→ dbt hỏi adapter → chọn `duckdb`. Sinh ra `dbt_project.yml` + skeleton `models/`.

**2. Cấu hình `profiles.yml`** (kết nối DuckDB — path relative tới project):
```yaml
# dbt_project/profiles.yml
logistics:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ../data/warehouse.duckdb
      schema: main
      threads: 4
```

**3. Khai báo source `raw`** trong `models/staging/_sources.yml`:
```yaml
version: 2
sources:
  - name: raw
    schema: raw
    tables:
      - name: data_shippingorder_now
      - name: dim_province
      - name: dim_district
      - name: dim_warehouse
      - name: dim_client
      - name: dim_shipper
      - name: dim_date
      - name: data_inside_history
      - name: data_transportation
      - name: data_shipment
      - name: data_cod
```

**4. Test kết nối:**
```
PS> dbt debug
```
→ `All checks passed!`
⚠ Nếu `Could not find profile` → đảm bảo `profiles.yml` nằm trong `dbt_project/` và tên profile khớp `dbt_project.yml`.

---

### Bước 2.3 — Build staging models `[CHƯA BUILD]`

**Layout 3 tầng** (theo CLAUDE.md project):
```
staging/ (view — clean + rename + cast, KHÔNG join)
    ↓
core/    (table — join dim, dedup, business logic)
    ↓
mart/    (table — pre-aggregate cho dashboard, partition week_start)
```

**Template staging** — chú ý dùng **tên cột thật** từ generator (`weight` gram, `created_date`, `dt`, `_data_quality`):
```sql
-- dbt_project/models/staging/stg_shippingorder.sql
-- Engine: DuckDB
{{ config(materialized='view') }}

WITH ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY order_code ORDER BY created_date DESC) AS rn
  FROM {{ source('raw', 'data_shippingorder_now') }}
  WHERE order_code IS NOT NULL
)

SELECT
  order_code,
  shop_id,
  client_id,
  created_date::TIMESTAMP                       AS created_date,
  dt::DATE                                       AS order_date,
  from_district_id,
  to_district_id,
  pick_warehouse_id,
  deliver_warehouse_id,
  current_warehouse_id,
  return_warehouse_id,
  pick_user                                      AS pick_shipper_id,
  deliver_user                                   AS deliver_shipper_id,
  weight                                         AS weight_gram,
  converted_weight                               AS converted_weight_gram,
  service_type_id,
  cod_amount                                     AS cod_amount_vnd,
  status,
  type_order,
  deliver_shift,
  is_sla_breach,
  failure_reason,
  _data_quality
FROM ranked
WHERE rn = 1   -- dedup duplicate order_code (heavy issue), giữ bản mới nhất
```
> Staging KHÔNG filter heavy issue — để mart/core tự quyết. Chỉ dedup PK + bỏ row vô nghĩa.
> Project quy ước: **không `SELECT *`** kể cả staging — list cột tường minh. Engine declare dòng đầu.

**Chạy + test staging:**
```
PS> dbt run  --select staging
```
→ `Completed successfully` — mỗi model 1 dòng `OK created view ...`.
```
PS> dbt test --select staging
```
→ Các test `not_null`, `unique`, `accepted_values` → `PASS`.

**File test đi kèm** (`models/staging/_staging.yml`):
```yaml
version: 2
models:
  - name: stg_shippingorder
    columns:
      - name: order_code
        tests: [not_null, unique]
      - name: status
        tests:
          - accepted_values:
              values: ['ready_to_pick','picking','in_transit','delivering',
                       'delivered','return_to_sender','cancelled']
      - name: weight_gram
        tests:
          - dbt_utils.expression_is_true:
              expression: ">= 0"
```
> `accepted_values` phải khớp enum thật trong [`config.py`](../src/generators/config.py) (`ORDER_STATUS_TERMINAL` + `ORDER_STATUS_ACTIVE`). Lưu ý generator còn inject enum drift `DONE`/`FINISH` (deprecated) — staging nên map về giá trị chuẩn hoặc test sẽ fail.

---

### Bước 2.4 — Build mart models `[CHƯA BUILD]`

**Template mart KPI** (đây là output ETL — chưa tồn tại; **đừng nhầm là đã có sẵn**):
```sql
-- dbt_project/models/mart/mart_daily_kpi.sql
-- Engine: DuckDB
{{ config(materialized='table') }}

SELECT
  order_date,
  p_from.region_fullname                                AS from_region,
  COUNT(*)                                              AS total_shipments,
  COUNT(*) FILTER (WHERE status = 'delivered')          AS delivered,
  COUNT(*) FILTER (WHERE is_sla_breach = true)          AS sla_breach,
  ROUND(COUNT(*) FILTER (WHERE status='delivered')*100.0 / COUNT(*), 2)  AS delivery_rate_pct,
  ROUND(COUNT(*) FILTER (WHERE is_sla_breach=true)*100.0 / COUNT(*), 2)  AS sla_breach_rate_pct,
  SUM(cod_amount_vnd)                                   AS total_cod_vnd,
  COUNT(*) FILTER (WHERE _data_quality = 'heavy_issue') AS quarantine_count
FROM {{ ref('stg_shippingorder') }} s
LEFT JOIN {{ ref('stg_warehouse') }} w  ON s.pick_warehouse_id = w.warehouse_id
LEFT JOIN {{ ref('dim_province') }} p_from ON w.province_id = p_from.province_id
WHERE _data_quality != 'heavy_issue'   -- heavy → quarantine, không vào mart
GROUP BY 1, 2
ORDER BY 1 DESC
```

**Chạy toàn bộ pipeline dbt theo thứ tự:**
```
PS> dbt run  --select staging   # 1. staging trước
PS> dbt run  --select core      # 2. core nếu staging OK
PS> dbt run  --select mart      # 3. mart
PS> dbt test                    # 4. full test suite
```
→ `dbt test`: `PASS=N WARN=0 ERROR=0`. Đây là điều kiện ra Phase 2.
⚠ Nếu `unique_stg_shippingorder_order_code` FAIL → staging chưa dedup. Kiểm tra `ROW_NUMBER() ... WHERE rn=1` (Bước 2.3).

**Xem mart đã build chưa, query thử:**
```
PS> python -c "import duckdb; con=duckdb.connect('data/warehouse.duckdb', read_only=True); print(con.execute('SELECT * FROM main.mart_daily_kpi LIMIT 5').df())"
```
→ Vài dòng KPI theo ngày × region.

### ⛔ GATE Phase 2 → Phase 3 (phải đạt TẤT CẢ)

```
□ load_to_duckdb.py chạy xong, row count DuckDB == parquet
□ dbt debug → All checks passed
□ dbt run --select staging/core/mart → không error (warning OK)
□ dbt test → PASS 100%, không FAIL
□ Query được mart_daily_kpi từ DuckDB, số liệu reasonable
□ Không hardcode absolute path (không C:\Users\... trong code)
```

---

# PHASE 3 — AIRFLOW (ORCHESTRATION)

> `[CHƯA BUILD]` — Phase này sẽ tạo: `airflow/dags/logistics_daily.py`, `src/quality_check.py`,
> service Airflow trong `docker/docker-compose.yml`.

### Checklist đầu vào Phase 3

```
□ Phase 2 gate pass — dbt pipeline chạy được bằng tay
□ Docker Desktop đã cài và đang chạy (kiểm tra: docker ps)
```

**Kiểm tra Docker:**
```
PS> docker ps
```
→ Bảng container (có thể rỗng). Nếu lỗi → mở Docker Desktop, đợi nó chạy.

---

### Bước 3.1 — Viết DAG `[CHƯA BUILD: airflow/dags/logistics_daily.py]`

Airflow **không build gì** — nó orchestrate các bước đã có ở Phase 1–2.
DAG = script Python định nghĩa thứ tự + dependency.

```python
# airflow/dags/logistics_daily.py
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {"owner": "data-engineer", "retries": 2,
                "retry_delay": timedelta(minutes=5)}

with DAG(
    dag_id="logistics_daily",
    default_args=default_args,
    schedule_interval="0 6 * * *",     # 6h sáng mỗi ngày
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["logistics", "daily"],
) as dag:
    generate = BashOperator(task_id="generate",
        bash_command="cd /opt/airflow/src/generators && python generate_all.py --seed 42")
    load = BashOperator(task_id="load_to_duckdb",
        bash_command="python /opt/airflow/src/load_to_duckdb.py")
    dbt_run = BashOperator(task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt_project && dbt run")
    dbt_test = BashOperator(task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt_project && dbt test")
    quality = BashOperator(task_id="quality_check",
        bash_command="python /opt/airflow/src/quality_check.py")

    generate >> load >> dbt_run >> dbt_test >> quality   # dependency chain
```

**4 câu hỏi tự kiểm:**
```
□ Nếu dbt_run fail, pipeline dừng? (cần on_failure_callback nếu muốn alert)
□ Retry đủ chưa? 2 lần, delay 5 phút — hợp lý?
□ DAG idempotent chưa? (chạy lại cùng ngày có duplicate data không?)
□ Airflow access được file DuckDB chưa? (volume mount đúng path chưa?)
```

---

### Bước 3.2 — Chạy Airflow qua Docker `[CHƯA BUILD]`

```
PS> docker-compose -f docker\docker-compose.yml up -d airflow
```
→ Container `airflow` lên trạng thái `Up`. Đợi ~1–2 phút.

**Xem log khởi động:**
```
PS> docker logs -f <airflow_container_name>
```
→ Khi thấy `Listening at: http://0.0.0.0:8080` là sẵn sàng. `Ctrl+C` để thoát log (không tắt container).

**Mở UI:** trình duyệt → `http://localhost:8080` → login → tìm DAG `logistics_daily`.

**Trigger thủ công 1 lần** (test end-to-end):
- Trong UI: bật toggle DAG → bấm nút ▶ (Trigger DAG).
- Hoặc CLI trong container:
```
PS> docker exec -it <airflow_container_name> airflow dags trigger logistics_daily
```
→ 5 task chuyển xanh lần lượt: `generate → load → dbt_run → dbt_test → quality_check`.
⚠ Nếu DAG không hiện trong UI → có import error. Xem:
```
PS> docker exec -it <airflow_container_name> airflow dags list-import-errors
```

### ⛔ GATE Phase 3 → Phase 4

```
□ DAG hiện trong Airflow UI, không import error
□ Trigger thủ công 1 lần thành công end-to-end (5 task xanh)
□ Log task không có unhandled exception
□ Nếu 1 step fail, retry tự chạy (không treo pipeline)
```

---

# PHASE 4 — METABASE (SERVE / DASHBOARD)

> `[CHƯA BUILD]` — Phase này sẽ tạo: service Metabase trong `docker/docker-compose.yml`,
> tải `metabase-duckdb-driver.jar`, build 4 dashboard, export JSON vào `metabase/dashboards/`.

### Checklist đầu vào Phase 4

```
□ Phase 2 gate pass — mart tables có data trong DuckDB
□ Docker đang chạy (docker ps)
□ Port 3000 trống (kiểm tra dưới)
□ Đã tải metabase-duckdb-driver.jar (community JDBC driver)
```

**Kiểm tra port 3000 trống:**
```
PS> netstat -ano | findstr :3000
```
→ **Không in gì** = port trống (tốt). Nếu có dòng → có app đang chiếm, đổi port hoặc tắt app đó.

---

### Bước 4.1 — Khởi động Metabase `[CHƯA BUILD]`

**1. Up service** (mount DuckDB read-only, driver vào `/plugins/`):
```
PS> docker-compose -f docker\docker-compose.yml up -d metabase
```
→ Container `metabase` trạng thái `Up`.

**2. Đợi Metabase khởi động (~2 phút), xem log:**
```
PS> docker logs -f <metabase_container_name>
```
→ Thấy `Metabase Initialization COMPLETE` là xong. `Ctrl+C` thoát log.

**3. Mở UI + setup admin:**
- Trình duyệt → `http://localhost:3000`
- First-time: tạo admin account (email + password bất kỳ, dùng để demo).

**4. Add database connection:**
```
Database type : DuckDB
File path     : /data/warehouse.duckdb     ← path TRONG container, không phải host
Read-only     : true
```
→ Test connection → `Success`.

⚠ **Connection fail** → debug theo checklist:
```
□ metabase-duckdb-driver.jar đã copy vào /plugins/ của container chưa?
□ Volume mount đúng? host: ./data/warehouse.duckdb → container: /data/warehouse.duckdb
□ File db tồn tại ở host? (dir data\warehouse.duckdb)
□ Đã restart sau khi thêm driver? (docker-compose restart metabase)
```
⚠ **DuckDB lock** giữa Airflow (write) và Metabase (read): DuckDB single-writer.
Fix: Metabase connect `read_only=true`, hoặc export mart ra parquet riêng cho Metabase đọc.

---

### Bước 4.2 — Build 4 dashboard `[CHƯA BUILD]`

Theo CLAUDE.md project — **4 dashboard bắt buộc**, build theo thứ tự ưu tiên:

```
1. KPI Overview (ops xem hàng ngày)
   - Total shipments hôm qua · Delivery success rate % · SLA breach rate % · Total COD
2. Hub Performance (manager xem tuần)
   - Throughput từng KTC (bar) · Regional breakdown · Top 5 KTC breach cao nhất
3. SLA Analysis (analyst drill-down)
   - Breach rate theo region × route · Trend 4 tuần · Day-of-week pattern
4. COD Reconciliation (finance)
   - Collection rate tháng · Pending COD by shipper · Disputed cases
```

**Cách build 1 card trong Metabase UI:**
- `+ New` → `Question` → chọn DuckDB DB → chọn table `mart_daily_kpi`
- Hoặc `Native query` (SQL trực tiếp), ví dụ:
```sql
-- Engine: DuckDB
SELECT order_date, total_shipments, delivery_rate_pct, sla_breach_rate_pct
FROM main.mart_daily_kpi
WHERE order_date >= CURRENT_DATE - INTERVAL 30 DAY
ORDER BY order_date
```
- Chọn visualization (line/bar/number) → `Save` → `Add to dashboard`.

**Nguyên tắc dashboard:**
- Mỗi chart trả lời đúng 1 câu hỏi
- Số quan trọng nhất ở góc trên-trái (mắt nhìn vào đó đầu tiên)
- Filter ngày là bắt buộc — không ai xem all-time
- Màu nhất quán: đỏ = bad, xanh = good (đừng đảo ngược)

**Export dashboard để version control:**
- Metabase `Settings → Export` → lưu JSON vào `metabase/dashboards/`.

### ⛔ GATE Phase 4 → Phase 5

```
□ 4 dashboard mở được trên localhost:3000
□ Mỗi dashboard ≥ 1 filter (ngày hoặc region)
□ KPI số khớp query SQL trực tiếp vào DuckDB (verify ≥ 2 con số)
□ Dashboard load < 3 giây
□ Screenshot ≥ 2 dashboard lưu vào docs/screenshots/ (cho README)
□ JSON dashboard export vào metabase/dashboards/
```

---

# PHASE 5 — DOCKER FULL STACK + DEMO + BÁO CÁO

> `[CHƯA BUILD]` — Phase này gói toàn bộ thành `docker-compose up` duy nhất.

### Checklist đầu vào Phase 5

```
□ Phase 4 gate pass — 4 dashboard live
□ Có ≥ 3 insight cụ thể từ data (số liệu, không phải nhận xét chung)
□ Trả lời được: "Con số X lấy từ bảng nào, query thế nào?"
```

---

### Bước 5.1 — Full stack một lệnh `[CHƯA BUILD: docker-compose.yml root]`

**Mục tiêu:** recruiter clone repo → 3 lệnh → dashboard live < 5 phút.

```
PS> python src\generators\generate_all.py --seed 42   # 1. sinh data
PS> python src\load_to_duckdb.py                       # 2. load DuckDB
PS> docker-compose up -d                               # 3. Airflow + Metabase
```
→ Sau ~3 phút: `http://localhost:3000` có 4 dashboard.

**Verify fresh-clone** (giả lập recruiter):
```
PS> docker-compose down -v        # tắt + xóa volume
PS> docker-compose up -d          # lên lại từ đầu
PS> docker ps                     # cả airflow + metabase đều Up
```

---

### Bước 5.2 — Chuẩn bị demo (script 3 phút)

**Checklist trước demo:**
```
□ Pipeline end-to-end không lỗi (generate → dbt → Metabase hiển thị đúng)
□ Data có dirty rows như thiết kế (verify bằng query _data_quality)
□ dbt test pass hết (KHÔNG demo với failing test)
□ Dashboard load < 2 giây
□ Có sẵn câu trả lời câu hỏi khó:
   - "Con số này từ đâu?" → chỉ vào dbt model
   - "Sao thấp hơn hệ thống kia?" → giải thích clean logic (heavy issue bị loại)
   - "Thêm filter X được không?" → biết mart schema để trả lời
```

**Script demo:**
```
1. (30s) Bài toán: "Team cần monitor vận hành hàng ngày — trước đây query SQL tay"
2. (1') Architecture: chỉ diagram. "Generator → DuckDB → dbt → Metabase.
        56M rows, chạy tự động 6h sáng qua Airflow."
3. (1') Dashboard: mở KPI → "Hôm qua X đơn, Y% success, Z% SLA breach"
        click Hub → "KTC HY01 breach cao bất thường → ops investigate ngay"
4. (30s) Data quality: "Pipeline có quality gate — dirty data flag + route quarantine,
        không lọt vào dashboard. dbt test pass 100%."
```

---

### Bước 5.3 — Báo cáo kỹ thuật (1 trang gửi manager)

```markdown
## Logistics Analytics Platform — Kết quả Phase X
**Tổng quan:** Pipeline end-to-end, 5M đơn synthetic mô phỏng GHN. Dashboard localhost:3000.
**Đã xong:**
- Generator: 5M shipments + ~40M events, reproducible với seed cố định
- Data quality: 3-tier dirty (heavy/light/outlier), dbt test 100% pass
- dbt models: staging → core → mart
- Airflow DAG: tự động 6h sáng
- Metabase: 4 dashboard (KPI / Hub / SLA / COD)
**Phát hiện từ data (ví dụ):**
- KTC HY01 SLA breach 22% — gấp đôi benchmark
- 8% đơn in_transit chưa assign shipper — ops gap
**Vấn đề & cách giải:**
- DuckDB lock Airflow×Metabase → Metabase dùng read_only connection
**Bước tiếp theo:**
- [ ] Alert Slack khi KPI vượt threshold
- [ ] Performance test 10M rows
```

---

### Bước 5.4 — Self-review trước khi báo "done"

```
CODE QUALITY
□ README đủ để người khác setup được không?
□ Code comment giải thích WHY (không phải WHAT) ở chỗ phức tạp?
□ Generator reproducible? (cùng seed → cùng output)
□ Không hardcode path tuyệt đối (C:\Users\...)?

DATA QUALITY
□ dbt test pass 100%?
□ Row count khớp generator output ↔ DuckDB?
□ Dirty data flag đúng (_data_quality)?

PIPELINE
□ Chạy lại từ fresh state không lỗi?
□ 1 step fail giữa chừng, retry có safe?

DASHBOARD
□ Mỗi chart có title rõ?
□ Filter ngày hoạt động?
□ Số khớp query SQL trực tiếp?

DOCUMENTATION
□ architecture.md phản ánh đúng code hiện tại?
□ data-model.md đủ để onboard người mới?
□ processing.md cập nhật trạng thái mới nhất?
```

### ⛔ GATE "Project Done" — trước khi báo recruiter

```
REPRODUCIBILITY
□ Người khác clone + theo README → setup thành công (không cần hỏi)
□ generate_all.py --seed 42 → cùng output mọi lần
□ Không có binary lớn trong git (parquet/duckdb) — chỉ sample 50k

QUALITY
□ dbt test pass 100%
□ Quarantine table có rows → chứng minh dirty data được catch
□ Great Expectations suite chạy không lỗi

DEMO READINESS
□ docker-compose up -d → Metabase live < 3 phút
□ 4 dashboard mở được, filter hoạt động, số reasonable
□ Giải thích được lineage: mart ← core ← staging ← raw

PORTFOLIO SIGNAL
□ README có architecture diagram + screenshot + quick start (≤ 3 bước)
□ Folder clean: không file thừa, không __pycache__ trong git
□ Commit history có ý nghĩa (không "fix fix fix")
```

---

# PHẦN PHỤ — DEBUG KHI GẶP VẤN ĐỀ

> Phần thực tế nhất. Mọi project đều gặp vấn đề — cách bạn xử lý nói lên trình độ.
> Dưới đây là các lỗi THẬT đã gặp trong project này (ghi trong `processing.md`).

### Framework debug 6 bước

```
1. REPRODUCE  — tái tạo lỗi với data nhỏ nhất:  python generate_all.py --sample
2. ISOLATE    — tách component:  --only dim  /  --only shippingorder
3. READ ERROR — đọc dòng cuối stack trace (file + số dòng), đừng đoán
4. SEARCH     — Google nguyên văn error message + tên tool
5. MINIMAL    — reproduce trong 10 dòng. Không reproduce được = chưa hiểu vấn đề
6. ASK        — sau 30 phút bí, hỏi senior kèm: error + đã thử gì + minimal example
```

### Lỗi thật đã gặp & cách fix (từ Phase 1)

**`UnicodeEncodeError: 'charmap' codec...`** (in tên kho tiếng Việt)
→ Quên bật UTF-8. Chạy `$env:PYTHONUTF8=1` trước khi chạy generator.

**Generator chạy cực chậm** (loop per-order, vd `_assign_dates` mất 2578s cho 500 đơn)
→ Đừng dùng Python for-loop qua hàng triệu row. Vectorize bằng numpy:
```python
# SAI: for i in range(n): rows.append({...})       # copy DataFrame mỗi vòng
# ĐÚNG: tạo toàn bộ array trước, 1 lần rng.choice(..., size=n, p=weights)
```

**Nhiều `python.exe` ngốn 2–3GB RAM mỗi con** (từ lần chạy cũ chưa kill)
→ Kill hết trước khi chạy lại:
```
PS> Stop-Process -Name python -Force
```

**`FutureWarning: set None trên float64/bool column`**
→ Cast sang object trước khi set None: `df[col] = df[col].astype(object)` (đã fix trong `_dirty.py`).

**`kwargs.get("x", pd.read_parquet(...))` đọc file thừa** (eager eval ngay cả khi đã pass df)
→ Dùng `x = kwargs.get("x"); if x is None: x = pd.read_parquet(...)`.

**Network timeout khi `pip install`**
→ `pip install --timeout 300 ...` hoặc cài từng batch nhỏ.

### Lỗi sẽ gặp ở Phase 2–4 (dự phòng)

**dbt `unique_..._order_code` FAIL** → staging chưa dedup. Thêm `ROW_NUMBER() OVER(...) WHERE rn=1`.

**DuckDB `Could not set lock on file`** → 2 process cùng mở db. Reader connect `read_only=True`.

**Metabase connection fail** → driver `.jar` chưa vào `/plugins/`, hoặc volume mount sai path, hoặc chưa restart container.

**Mart query chậm / Metabase timeout** → mart phải là `materialized='table'` (không phải view); pre-filter 90 ngày gần nhất.

---

## Tóm tắt 1 trang — lệnh cốt lõi từng phase

```
PHASE 0 — HIỂU BÀI TOÁN
  (không gõ lệnh) viết my-understanding.md + entity map + chọn kiến trúc
  ⛔ GATE: viết lại được đề + kiến trúc có lý do + architecture.md tồn tại

PHASE 1 — GENERATE  ✅ ĐÃ BUILD
  cd project; python -m venv .venv; .\.venv\Scripts\Activate.ps1
  pip install --timeout 120 -r requirements.txt
  cd src\generators; $env:PYTHONUTF8=1
  python _test_smoke.py                  # smoke test
  python generate_all.py --sample        # 10k verify
  python generate_all.py --seed 42       # full 56M rows
  ⛔ GATE: 11 parquet, reproducible, _data_quality 3 nhóm, sample 50k commit

PHASE 2 — DuckDB + dbt  [CHƯA BUILD]
  python src\load_to_duckdb.py
  cd dbt_project; dbt debug
  dbt run --select staging; dbt run --select core; dbt run --select mart
  dbt test
  ⛔ GATE: dbt test PASS 100%, mart query được

PHASE 3 — AIRFLOW  [CHƯA BUILD]
  docker-compose -f docker\docker-compose.yml up -d airflow
  → localhost:8080, trigger logistics_daily, 5 task xanh
  ⛔ GATE: DAG end-to-end pass, retry hoạt động

PHASE 4 — METABASE  [CHƯA BUILD]
  netstat -ano | findstr :3000           # check port
  docker-compose -f docker\docker-compose.yml up -d metabase
  → localhost:3000, add DuckDB (read-only), build 4 dashboard
  ⛔ GATE: 4 dashboard live, số khớp SQL, screenshot

PHASE 5 — FULL STACK + DEMO  [CHƯA BUILD]
  generate_all.py --seed 42 → load_to_duckdb.py → docker-compose up -d
  ⛔ DONE: fresh clone < 5 phút có dashboard, dbt test pass, README đủ
```

---

## Tài liệu tham chiếu trong project

| Tài liệu | Layer | Mô tả |
|---|---|---|
| [architecture.md](architecture.md) | — | Flow diagram + layer responsibility + Metabase setup |
| [entity-map.md](entity-map.md) | — | **Đọc trước tiên** — 9 entity, business flows, câu hỏi analytics |
| [data-model.md](data-model.md) | **Bronze (source)** | Schema raw data sinh ra: 5 dim + 5 fact, column names/types, grain, volume |
| [data-quality-strategy.md](data-quality-strategy.md) | Bronze | Taxonomy dirty data + tỷ lệ inject + implementation guide |
| [../README.md](../README.md) | — | Quick start + tech stack + roadmap |
| [../processing.md](../processing.md) | — | Tiến trình hiện tại + nhật ký lỗi thật + quyết định quan trọng |
| [../src/generators/](../src/generators/) | Bronze | Code generator từng bảng (config.py = constants dùng chung) |
| [../dbt_project/models/](../dbt_project/models/) | Silver/Gold/Mart | dbt staging/core/mart — **đây mới là ETL output** `[CHƯA BUILD]` |
```
