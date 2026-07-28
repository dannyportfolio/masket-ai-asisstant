from pathlib import Path

import pandas as pd

from trading_assistant.market_breadth import compute_market_breadth
from trading_assistant.market_data.base import normalize_ohlcv_frame
from trading_assistant.market_data.cache import MarketDataCache
from trading_assistant.market_data.providers import IDXLicensedFileProvider


def test_normalization_keeps_provenance():
    frame = normalize_ohlcv_frame(pd.DataFrame({"Date": ["2026-01-02"], "Open": [1], "High": [2], "Low": [1], "Close": [2], "Volume": [10]}), ticker="BBCA.JK", source="test", interval="1d", is_delayed=True, delay_seconds=60)
    assert frame.iloc[0]["source"] == "test"
    assert frame.iloc[0]["exchange"] == "IDX"
    assert frame.iloc[0]["delay_seconds"] == 60


def test_breadth_marks_partial_coverage():
    frame = pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "close": [10, 11], "volume": [100, 120]})
    result, latest = compute_market_breadth({"AAA.JK": frame}, 2)
    assert latest["status"] == "PARTIAL_COVERAGE"
    assert result.iloc[-1]["advancers"] == 1


def test_licensed_provider_is_disabled_without_directory(tmp_path: Path):
    assert not IDXLicensedFileProvider(tmp_path / "missing").is_available()
