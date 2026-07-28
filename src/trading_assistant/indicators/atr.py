from __future__ import annotations

import pandas as pd


def add_atr(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    result = df.copy()
    high = pd.to_numeric(result["high"], errors="coerce")
    low = pd.to_numeric(result["low"], errors="coerce")
    close = pd.to_numeric(result["close"], errors="coerce")
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    result[f"atr_{window}"] = true_range.rolling(window, min_periods=window).mean()
    return result
