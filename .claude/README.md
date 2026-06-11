# .claude — Project 02 Logistics Analytics Platform

Cấu hình Claude Code **riêng cho project 02**. Override các quy ước workspace nếu cần.

## Cấu trúc

| Folder / File | Mục đích |
|---|---|
| `settings.json` | Permission + env riêng cho project (cho phép `dbt`, `duckdb`, `airflow`, `pytest`) |
| `agents/` | Sub-agent riêng cho data pipeline (data-generator, dbt-modeler, dashboard-builder) |
| `commands/` | Slash command project-scope (`/gen-data`, `/build-marts`, `/refresh-dashboard`) |
| `skills/` | Skill tái sử dụng trong pipeline (DuckDB query, dbt run, parquet export) |
| `hooks/` | Hook tự động (vd: chặn write vào `data/raw/`, validate trước khi commit) |
| `templates/` | Template scaffold (generator script, dbt model, mart JSON export) |

## Nguyên tắc

- File lớn (`.duckdb`, `data/raw/*.parquet`) **không được Edit/Write** — đã chặn trong `settings.json`
- Mọi đọc file CSV/Parquet/Excel **bắt buộc** spawn `analyst` sub-agent (theo `file-analysis.md`)
- Tiến trình cập nhật ở `processing.md` cùng cấp — không lưu vào memory folder
- Override quy ước workspace bằng `CLAUDE.md` ở root project (cùng cấp với folder này)

## Khi tạo agent / command mới

1. Đặt file vào folder tương ứng (`agents/<name>.md`, `commands/<name>.md`)
2. Mỗi file phải có frontmatter `name`, `description`, `tools` (với agent)
3. Naming kebab-case
4. Không trùng tên với agent/command ở root `.claude/`
