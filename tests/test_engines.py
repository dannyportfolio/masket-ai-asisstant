from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading_assistant.engines import enrich_market_frame


def _market_frame(rows: int = 260) -> pd.DataFrame:
    sequence = np.arange(rows, dtype=float)
    close = 1_000 + sequence * 1.5 + np.sin(sequence / 7) * 10
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-01-01", periods=rows, freq="B").astype(str),
            "open": close - 2,
            "high": close + 8,
            "low": close - 8,
            "close": close,
            "adj_close": close,
            "volume": 1_000_000 + (sequence % 30) * 20_000,
            "ticker": "TEST.JK",
            "source": "test",
        }
    )


def test_native_engine_preserves_phase1_contract() -> None:
    result = enrich_market_frame(_market_frame(), "native")

    assert result.status == "OK"
    assert result.used_engine == "native"
    assert {
        "cmf_10",
        "cmf_20",
        "cmf_60",
        "atr_14",
        "volume_ratio_20",
    }.issubset(result.frame.columns)
    assert not any(column.startswith("ma_") for column in result.frame.columns)


def test_fincept_engine_adds_indicators_and_maps_legacy_contract() -> None:
    original = _market_frame()
    result = enrich_market_frame(original, "fincept")

    assert result.status == "OK", result.error
    assert result.used_engine == "fincept"
    assert result.frame.index.equals(original.index)
    assert {"rsi", "macd", "obv", "bb_hband", "cumulative_return"}.issubset(
        result.frame.columns
    )
    assert {"cmf_10", "cmf_20", "cmf_60", "atr_14"}.issubset(
        result.frame.columns
    )
    assert not any(
        column.lower().startswith(("ma_", "sma_", "ema_", "wma_"))
        or column.lower() in {"kama", "bb_mavg", "kc_mavg"}
        for column in result.frame.columns
    )
    pd.testing.assert_series_equal(
        result.frame["cmf_20"],
        result.frame["cmf"],
        check_names=False,
    )
    pd.testing.assert_series_equal(
        result.frame["atr_14"],
        result.frame["atr"],
        check_names=False,
    )


def test_fincept_failure_falls_back_without_breaking_contract(tmp_path) -> None:
    result = enrich_market_frame(
        _market_frame(),
        "fincept",
        fincept_script=tmp_path / "missing_compute_technicals.py",
    )

    assert result.status == "FALLBACK_NATIVE"
    assert result.requested_engine == "fincept"
    assert result.used_engine == "native"
    assert "Fincept technical engine is missing" in (result.error or "")
    assert {"cmf_20", "atr_14"}.issubset(result.frame.columns)
    assert not any(column.startswith("ma_") for column in result.frame.columns)


def test_short_history_falls_back_before_fincept_calculation() -> None:
    result = enrich_market_frame(_market_frame(rows=10), "fincept")

    assert result.status == "FALLBACK_NATIVE"
    assert result.used_engine == "native"
    assert "requires at least 60 bars" in (result.error or "")


def test_unknown_engine_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown analytics engine"):
        enrich_market_frame(_market_frame(), "other")
