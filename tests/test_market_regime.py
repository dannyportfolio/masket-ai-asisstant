from __future__ import annotations

import pandas as pd

from trading_assistant.market_regime import screen_ihsg_regime


def _trend_frame(up: bool = True, rows: int = 260) -> pd.DataFrame:
    prices = []
    for index in range(rows):
        base = 1000 + index * 2 if up else 1600 - index * 2
        prices.append(base)
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=rows, freq="B").strftime("%Y-%m-%d"),
            "open": [price - 2 for price in prices],
            "high": [price + 5 for price in prices],
            "low": [price - 5 for price in prices],
            "close": prices,
            "adj_close": prices,
            "volume": [1_000_000 + index * 1000 for index in range(rows)],
            "ticker": "^JKSE",
            "source": "Yahoo Finance",
        }
    )


def test_missing_ihsg_sets_macro_unverified() -> None:
    result, _ = screen_ihsg_regime(pd.DataFrame(), "DATA_MISSING")

    assert result.ihsg_regime == "DATA_MISSING"
    assert result.macro_permission == "MACRO_UNVERIFIED"


def test_bullish_ihsg_allows_long() -> None:
    result, prepared = screen_ihsg_regime(_trend_frame(up=True), "OK")

    assert not prepared.empty
    assert {"ma_20", "ma_50", "ma_200", "ma50_slope_10"}.issubset(prepared.columns)
    assert {"ma20", "ma50", "ma200", "ma50_slope_10"}.issubset(result.evidence)
    assert result.ihsg_trend_score > 0
    assert result.macro_permission in {"LONG_ALLOWED", "LONG_RESTRICTED"}


def test_bearish_ihsg_blocks_aggressive_long() -> None:
    result, _ = screen_ihsg_regime(_trend_frame(up=False), "OK")

    assert result.ihsg_trend_score < 0
    assert result.macro_permission in {"SHORT_OR_EXIT_ALLOWED", "WAIT_ONLY"}
