from __future__ import annotations

import numpy as np
import pandas as pd


def _rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    def percentile(values: np.ndarray) -> float:
        current = values[-1]
        if np.isnan(current):
            return np.nan
        valid = values[~np.isnan(values)]
        if len(valid) == 0:
            return np.nan
        return float((valid <= current).mean())

    return series.rolling(window=window, min_periods=max(5, window // 4)).apply(percentile, raw=True)


def add_basic_vpa(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    result = df.copy()
    high = pd.to_numeric(result["high"], errors="coerce")
    low = pd.to_numeric(result["low"], errors="coerce")
    open_ = pd.to_numeric(result["open"], errors="coerce")
    close = pd.to_numeric(result["close"], errors="coerce")
    volume = pd.to_numeric(result["volume"], errors="coerce")

    spread = high - low
    result["spread"] = spread
    result["body"] = (close - open_).abs()
    result["close_position"] = np.where(spread.to_numpy() == 0, 0.5, ((close - low) / spread).to_numpy())

    result["volume_baseline_20"] = volume.rolling(window=window, min_periods=max(5, window // 4)).mean()
    result["spread_baseline_20"] = spread.rolling(window=window, min_periods=max(5, window // 4)).mean()
    result["volume_ratio_20"] = volume / result["volume_baseline_20"]
    result["spread_ratio_20"] = spread / result["spread_baseline_20"]
    result["volume_percentile_20"] = _rolling_percentile(volume, window)
    result["spread_percentile_20"] = _rolling_percentile(spread, window)

    result["is_up_bar"] = close > open_
    result["is_down_bar"] = close < open_
    result["close_near_high"] = result["close_position"] >= 0.75
    result["close_near_low"] = result["close_position"] <= 0.25
    result["close_mid_range"] = result["close_position"].between(0.25, 0.75, inclusive="neither")
    result["wide_spread"] = result["spread_percentile_20"] >= 0.8
    result["narrow_spread"] = result["spread_percentile_20"] <= 0.2
    result["high_volume"] = result["volume_percentile_20"] >= 0.8
    result["low_volume"] = result["volume_percentile_20"] <= 0.2
    result["narrow_spread_high_volume"] = result["narrow_spread"] & result["high_volume"]
    result["wide_spread_up_bar"] = result["wide_spread"] & result["is_up_bar"]
    result["wide_spread_down_bar"] = result["wide_spread"] & result["is_down_bar"]
    result["effort_no_result_up"] = result["high_volume"] & result["is_up_bar"] & ~result["close_near_high"]
    result["effort_no_result_down"] = result["high_volume"] & result["is_down_bar"] & ~result["close_near_low"]
    result["low_effort_large_move"] = result["low_volume"] & result["wide_spread"]
    return add_vwpa(result, window=window)


def add_vwpa(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    result = df.copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    volume = pd.to_numeric(result["volume"], errors="coerce")
    traded_value = close * volume
    close_position = pd.to_numeric(
        result.get("close_position", pd.Series(index=result.index, dtype=float)),
        errors="coerce",
    ).fillna(0.5)
    pressure_multiplier = (close_position - 0.5) * 2
    value_pressure = traded_value * pressure_multiplier

    result["vwpa_traded_value"] = traded_value
    result["vwpa_value_pressure"] = value_pressure
    result["vwpa_value_baseline_20"] = traded_value.rolling(
        window=window,
        min_periods=max(5, window // 4),
    ).mean()
    result["vwpa_value_ratio_20"] = traded_value / result["vwpa_value_baseline_20"].replace(0, pd.NA)
    result["vwpa_value_percentile_20"] = _rolling_percentile(traded_value, window)
    rolling_pressure = value_pressure.rolling(window=window, min_periods=max(5, window // 4)).sum()
    rolling_value = traded_value.rolling(window=window, min_periods=max(5, window // 4)).sum()
    result["vwpa_pressure_20"] = rolling_pressure / rolling_value.replace(0, pd.NA)
    result["vwpa_signal"] = "NEUTRAL_VALUE_ACTION"
    result.loc[
        (result["vwpa_pressure_20"] >= 0.20) & (result["vwpa_value_percentile_20"] >= 0.60),
        "vwpa_signal",
    ] = "VALUE_ACCUMULATION_PRESSURE"
    result.loc[
        (result["vwpa_pressure_20"] <= -0.20) & (result["vwpa_value_percentile_20"] >= 0.60),
        "vwpa_signal",
    ] = "VALUE_DISTRIBUTION_PRESSURE"
    result.loc[
        result.get("narrow_spread_high_volume", False) & (result["vwpa_value_percentile_20"] >= 0.80),
        "vwpa_signal",
    ] = "VALUE_ABSORPTION_OR_CHURN"
    return result
