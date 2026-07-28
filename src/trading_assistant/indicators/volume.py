from __future__ import annotations

import pandas as pd


def add_volume_intelligence(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    volume = pd.to_numeric(result.get("volume", pd.Series(index=result.index, dtype=float)), errors="coerce")
    close = pd.to_numeric(result.get("close", pd.Series(index=result.index, dtype=float)), errors="coerce")
    for window in (5, 20, 60):
        result[f"volume_baseline_{window}"] = volume.rolling(window, min_periods=1).mean()
    result["relative_volume_20"] = volume / result["volume_baseline_20"].replace(0, pd.NA)
    result["volume_zscore_20"] = (volume - result["volume_baseline_20"]) / volume.rolling(20, min_periods=5).std().replace(0, pd.NA)
    result["volume_spike_20"] = result["relative_volume_20"] >= 2.0
    result["volume_acceleration_5_20"] = result["volume_baseline_5"] / result["volume_baseline_20"].replace(0, pd.NA)
    result["traded_value"] = close * volume
    result["return_1d"] = close.pct_change()
    result["return_5d"] = close.pct_change(5)
    result["volume_signal"] = "NONE"
    result.loc[(result["return_1d"] > 0) & (result["relative_volume_20"] >= 1.5), "volume_signal"] = "CONFIRMED_ADVANCE"
    result.loc[(result["return_1d"] < 0) & (result["relative_volume_20"] >= 1.5), "volume_signal"] = "BEARISH_DISTRIBUTION"
    result.loc[(result["return_1d"] > 0) & (result["relative_volume_20"] < 0.8), "volume_signal"] = "WEAK_RALLY"
    return result
