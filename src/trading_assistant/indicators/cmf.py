from __future__ import annotations

import numpy as np
import pandas as pd


def add_cmf(df: pd.DataFrame, windows: tuple[int, ...] = (10, 20, 60)) -> pd.DataFrame:
    result = df.copy()
    high = pd.to_numeric(result["high"], errors="coerce")
    low = pd.to_numeric(result["low"], errors="coerce")
    close = pd.to_numeric(result["close"], errors="coerce")
    volume = pd.to_numeric(result["volume"], errors="coerce").fillna(0)

    spread = high - low
    multiplier = np.where(
        spread.to_numpy() == 0,
        0.0,
        (((close - low) - (high - close)) / spread).to_numpy(),
    )
    result["money_flow_multiplier"] = pd.Series(multiplier, index=result.index).replace([np.inf, -np.inf], 0).fillna(0)
    result["money_flow_volume"] = result["money_flow_multiplier"] * volume

    for window in windows:
        mfv_sum = result["money_flow_volume"].rolling(window=window, min_periods=window).sum()
        vol_sum = volume.rolling(window=window, min_periods=window).sum()
        result[f"cmf_{window}"] = np.where(vol_sum.to_numpy() == 0, np.nan, (mfv_sum / vol_sum).to_numpy())

    return result
