from __future__ import annotations

import pandas as pd

from trading_assistant.indicators.cmf import add_cmf


def test_cmf_handles_zero_spread_and_zero_volume() -> None:
    df = pd.DataFrame(
        {
            "high": [10, 10, 12],
            "low": [10, 8, 10],
            "close": [10, 9, 11],
            "volume": [100, 0, 300],
        }
    )

    result = add_cmf(df, windows=(2,))

    assert result.loc[0, "money_flow_multiplier"] == 0
    assert result.loc[1, "cmf_2"] == 0
    assert result.loc[2, "cmf_2"] == 0


def test_cmf_calculates_expected_value() -> None:
    df = pd.DataFrame(
        {
            "high": [10, 12],
            "low": [8, 10],
            "close": [10, 11],
            "volume": [100, 300],
        }
    )

    result = add_cmf(df, windows=(2,))

    assert round(result.loc[1, "cmf_2"], 6) == 0.25
