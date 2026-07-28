from __future__ import annotations

import pandas as pd


def add_moving_averages(df: pd.DataFrame, windows: tuple[int, ...] = (20, 50, 200)) -> pd.DataFrame:
    result = df.copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    for window in windows:
        result[f"ma_{window}"] = close.rolling(window, min_periods=window).mean()
    return result
