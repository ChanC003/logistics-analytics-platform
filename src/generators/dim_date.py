"""
Generator: dim_date
Rows: 730 (2024-01-01 → 2025-12-31)
Output: data/raw/dim_date.parquet
Dependencies: none
"""
from pathlib import Path
import pandas as pd

# Ngày lễ VN (YYYY-MM-DD) trong 2024–2025
VN_HOLIDAYS = {
    # 2024
    "2024-01-01", "2024-02-08", "2024-02-09", "2024-02-10",
    "2024-02-11", "2024-02-12", "2024-02-13", "2024-02-14",
    "2024-04-18", "2024-04-30", "2024-05-01",
    "2024-09-02", "2024-09-03",
    # 2025
    "2025-01-01",
    "2025-01-28", "2025-01-29", "2025-01-30", "2025-01-31",
    "2025-02-01", "2025-02-02", "2025-02-03", "2025-02-04",
    "2025-04-07", "2025-04-30", "2025-05-01",
    "2025-09-01", "2025-09-02",
}

DOW_VN = {1: "Thứ 2", 2: "Thứ 3", 3: "Thứ 4", 4: "Thứ 5",
          5: "Thứ 6", 6: "Thứ 7", 7: "CN"}


def generate(seed: int = 42, **kwargs) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    df = pd.DataFrame({"date": dates})

    df["date_id"]       = df["date"].dt.strftime("%Y%m%d").astype(int)
    df["year"]          = df["date"].dt.year
    df["quarter"]       = df["date"].dt.quarter
    df["month"]         = df["date"].dt.month
    df["week_of_year"]  = df["date"].dt.isocalendar().week.astype(int)
    df["day_of_week"]   = df["date"].dt.dayofweek + 1   # 1=Mon … 7=Sun
    df["day_of_week_vn"] = df["day_of_week"].map(DOW_VN)
    df["is_weekend"]    = df["day_of_week"].isin([6, 7])
    df["is_holiday_vn"] = df["date"].dt.strftime("%Y-%m-%d").isin(VN_HOLIDAYS)
    df["date"]          = df["date"].dt.date   # store as date, not timestamp

    return df[["date_id", "date", "year", "quarter", "month",
               "week_of_year", "day_of_week", "day_of_week_vn",
               "is_weekend", "is_holiday_vn"]]


def write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="snappy", index=False)


if __name__ == "__main__":
    df = generate()
    out = Path("data/raw/dim_date.parquet")
    write(df, out)
    print(f"dim_date: {len(df)} rows → {out}")
