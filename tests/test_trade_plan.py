from __future__ import annotations

import pandas as pd

from trading_assistant.indicators.cmf import add_cmf
from trading_assistant.indicators.vpa import add_basic_vpa
from trading_assistant.trade_plan import build_trade_analysis


def _frame(rows: int = 120, start: float = 1000, step: float = 3) -> pd.DataFrame:
    prices = [start + index * step for index in range(rows)]
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=rows, freq="B").strftime("%Y-%m-%d"),
            "open": [price - 2 for price in prices],
            "high": [price + 8 for price in prices],
            "low": [price - 8 for price in prices],
            "close": prices,
            "adj_close": prices,
            "volume": [1_000_000 + index * 10_000 for index in range(rows)],
            "ticker": "TEST.JK",
            "source": "Yahoo Finance",
        }
    )


def _processed(df: pd.DataFrame) -> pd.DataFrame:
    return add_basic_vpa(add_cmf(df))


def test_trade_plan_blocks_buy_when_macro_wait_only() -> None:
    macro = {
        "ihsg_regime": "VOLATILE_UNCLEAR",
        "ihsg_trend_score": 0,
        "macro_permission": "WAIT_ONLY",
        "macro_reason": "unclear",
    }

    analysis = build_trade_analysis("TEST.JK", _processed(_frame()), "OK", macro, _processed(_frame()))

    assert analysis.trade_plan["trade_action"] == "WAIT"
    assert analysis.trade_plan["entry_type"] == "NO_ENTRY"


def test_trade_plan_downgrades_bearish_macro_to_watch() -> None:
    stock = _processed(_frame(step=5))
    ihsg = _processed(_frame(step=-2))
    macro = {
        "ihsg_regime": "BEARISH",
        "ihsg_trend_score": -65,
        "macro_permission": "SHORT_OR_EXIT_ALLOWED",
        "macro_reason": "bearish",
    }

    analysis = build_trade_analysis("TEST.JK", stock, "OK", macro, ihsg)

    assert analysis.relative_strength["relative_strength_status"] == "OUTPERFORMING_IHSG"
    assert analysis.trade_plan["trade_action"] in {"ACCUMULATION_WATCH", "WAIT"}
    assert analysis.trade_plan["trade_action"] != "BUY_SETUP"


def test_insufficient_data_has_no_entry() -> None:
    macro = {
        "ihsg_regime": "BULLISH",
        "ihsg_trend_score": 70,
        "macro_permission": "LONG_ALLOWED",
        "macro_reason": "bullish",
    }

    analysis = build_trade_analysis("TEST.JK", pd.DataFrame(), "DATA_INSUFFICIENT", macro, pd.DataFrame())

    assert analysis.trade_plan["trade_action"] == "DATA_INSUFFICIENT"
    assert analysis.trade_plan["entry_point"] is None
