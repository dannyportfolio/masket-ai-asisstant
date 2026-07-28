from __future__ import annotations

import pandas as pd

from trading_assistant.indicators.vpa import add_basic_vpa


def test_vpa_close_position_and_flags() -> None:
    df = pd.DataFrame(
        {
            "open": [10, 10, 10, 10, 10],
            "high": [12, 12, 12, 12, 12],
            "low": [10, 10, 10, 10, 10],
            "close": [12, 10, 11, 12, 10],
            "volume": [100, 200, 300, 400, 500],
        }
    )

    result = add_basic_vpa(df, window=5)

    assert result.loc[0, "close_near_high"]
    assert result.loc[1, "close_near_low"]
    assert result.loc[2, "close_mid_range"]
    assert "narrow_spread_high_volume" in result.columns


def test_vpa_zero_spread_uses_neutral_close_position() -> None:
    df = pd.DataFrame(
        {
            "open": [10, 10, 10, 10, 10],
            "high": [10, 10, 10, 10, 10],
            "low": [10, 10, 10, 10, 10],
            "close": [10, 10, 10, 10, 10],
            "volume": [100, 200, 300, 400, 500],
        }
    )

    result = add_basic_vpa(df, window=5)

    assert result["close_position"].eq(0.5).all()


def test_vwpa_flags_value_accumulation_pressure() -> None:
    df = pd.DataFrame(
        {
            "open": [10, 10, 10, 10, 10],
            "high": [12, 12, 12, 12, 12],
            "low": [10, 10, 10, 10, 10],
            "close": [12, 12, 12, 12, 12],
            "volume": [100, 150, 200, 250, 1_000],
        }
    )

    result = add_basic_vpa(df, window=5)

    assert result.loc[4, "vwpa_pressure_20"] > 0
    assert result.loc[4, "vwpa_signal"] == "VALUE_ACCUMULATION_PRESSURE"


def test_vwpa_flags_value_distribution_pressure() -> None:
    df = pd.DataFrame(
        {
            "open": [10, 10, 10, 10, 10],
            "high": [12, 12, 12, 12, 12],
            "low": [10, 10, 10, 10, 10],
            "close": [10, 10, 10, 10, 10],
            "volume": [100, 150, 200, 250, 1_000],
        }
    )

    result = add_basic_vpa(df, window=5)

    assert result.loc[4, "vwpa_pressure_20"] < 0
    assert result.loc[4, "vwpa_signal"] == "VALUE_DISTRIBUTION_PRESSURE"
