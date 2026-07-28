from __future__ import annotations

import pandas as pd

from trading_assistant.data_quality import evaluate_quality


def test_empty_data_is_missing() -> None:
    result = evaluate_quality(pd.DataFrame())

    assert result.status == "DATA_MISSING"
    assert "empty_dataset" in result.flags


def test_insufficient_rows_take_priority() -> None:
    df = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02"],
            "open": [1, 2],
            "high": [2, 3],
            "low": [1, 2],
            "close": [2, 3],
            "volume": [100, 0],
        }
    )

    result = evaluate_quality(df, min_bars=3)

    assert result.status == "DATA_INSUFFICIENT"
    assert any(flag.startswith("zero_volume_rows") for flag in result.flags)


def test_invalid_candle_is_data_anomaly() -> None:
    df = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "open": [1, 5, 2],
            "high": [2, 4, 3],
            "low": [1, 2, 2],
            "close": [2, 3, 3],
            "volume": [100, 100, 100],
        }
    )

    result = evaluate_quality(df, min_bars=3)

    assert result.status == "DATA_ANOMALY"
    assert any(flag.startswith("invalid_candle_rows") for flag in result.flags)
