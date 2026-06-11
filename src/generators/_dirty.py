"""
Shared dirty-data injection utilities.
Import từ mọi fact generator — không monkey-patch, không side-effect.
"""
import numpy as np
import pandas as pd


def inject_nulls(df: pd.DataFrame, column: str, rate: float,
                 condition: pd.Series = None) -> pd.DataFrame:
    """Set column → None cho rate% rows; nếu condition thì chỉ áp dụng trong subset đó."""
    rng_local = np.random.default_rng()   # stateless helper — caller dùng seed riêng
    mask = pd.Series(rng_local.random(len(df)) < rate, index=df.index)
    if condition is not None:
        mask = mask & condition
    df.loc[mask, column] = None
    return df, mask


def inject_nulls_seeded(df: pd.DataFrame, column: str, rate: float,
                         rng: np.random.Generator,
                         condition: pd.Series = None):
    """Inject nulls với seeded rng — dùng trong generator chính."""
    mask = pd.Series(rng.random(len(df)) < rate, index=df.index)
    if condition is not None:
        mask = mask & condition
    df[column] = df[column].astype(object)
    df.loc[mask, column] = None
    return df, mask


def inject_outliers(df: pd.DataFrame, column: str, rules: list,
                    rng: np.random.Generator) -> pd.DataFrame:
    """
    rules: list of dict với keys: pct, type, và tham số phụ.
    Supported types: range, negative, epoch_zero, future_days, decimal_shifted
    """
    for rule in rules:
        mask = rng.random(len(df)) < rule["pct"]
        t = rule["type"]
        if t == "range":
            lo, hi = rule["range"]
            df.loc[mask, column] = rng.integers(lo, hi, size=mask.sum())
        elif t == "negative":
            df.loc[mask, column] = -df.loc[mask, column].abs()
        elif t == "epoch_zero":
            df.loc[mask, column] = pd.Timestamp("1970-01-01")
        elif t == "future_days":
            lo_d, hi_d = rule.get("days_ahead", (1, 30))
            offsets = pd.to_timedelta(rng.integers(lo_d, hi_d, size=mask.sum()), unit="D")
            df.loc[mask, column] = pd.Timestamp("2026-01-01") + offsets
        elif t == "decimal_shifted":
            df.loc[mask, column] = df.loc[mask, column] * rule.get("factor", 1000)
        elif t == "zero":
            df.loc[mask, column] = 0
    return df


def inject_duplicates(df: pd.DataFrame, pk_col: str, rate: float,
                      rng: np.random.Generator) -> pd.DataFrame:
    """Duplicate một số rows để tạo duplicate PK."""
    n = max(1, int(len(df) * rate))
    idx = rng.choice(len(df), size=n, replace=False)
    dup_rows = df.iloc[idx].copy()
    return pd.concat([df, dup_rows], ignore_index=True)


def inject_enum_drift(df: pd.DataFrame, column: str, old_values: list,
                      rate: float, rng: np.random.Generator) -> pd.DataFrame:
    """Thay một số giá trị enum mới bằng giá trị cũ / deprecated."""
    mask = rng.random(len(df)) < rate
    df.loc[mask, column] = rng.choice(old_values, size=mask.sum())
    return df, mask


def flag_quality(df: pd.DataFrame,
                 heavy_mask: pd.Series,
                 light_mask: pd.Series) -> pd.DataFrame:
    """Gán cột _data_quality: heavy > light > clean."""
    df["_data_quality"] = "clean"
    df.loc[light_mask & ~heavy_mask, "_data_quality"] = "light_issue"
    df.loc[heavy_mask, "_data_quality"] = "heavy_issue"
    return df
