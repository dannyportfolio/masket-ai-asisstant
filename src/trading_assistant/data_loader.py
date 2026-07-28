from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from trading_assistant.market_data.base import MarketDataResult, NORMALIZED_COLUMNS, normalize_ohlcv_frame
from trading_assistant.market_data.registry import build_default_registry


RAW_COLUMNS = NORMALIZED_COLUMNS
FetchResult = MarketDataResult


def normalize_yahoo_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)

    df = frame.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df = df.reset_index()
    rename_map = {
        "Date": "date",
        "Datetime": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    }
    df = df.rename(columns=rename_map)
    if "adj_close" not in df.columns:
        df["adj_close"] = pd.NA

    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date.astype("string")
    df["ticker"] = ticker
    df["source"] = "Yahoo Finance"
    return normalize_ohlcv_frame(df, ticker=ticker, source="Yahoo Finance", interval="1d",
                                 is_delayed=True, delay_seconds=None)


def configure_yfinance_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yf.cache.set_tz_cache_location(str(cache_dir))
    except AttributeError:
        pass


def fetch_ohlcv(ticker: str, period: str, interval: str, cache_dir: Path | None = None,
                provider_registry=None) -> FetchResult:
    if provider_registry is None and cache_dir is not None:
        provider_registry = build_default_registry(cache_dir.parent if cache_dir.name == "yfinance" else cache_dir,
                                                   provider_priority=("yahoo",))
    if provider_registry is not None:
        return provider_registry.fetch(ticker, period, interval)
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        if cache_dir is not None:
            configure_yfinance_cache(cache_dir)
        raw = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
        df = normalize_yahoo_frame(raw, ticker)
        status = "DATA_MISSING" if df.empty else "FETCHED"
        error = None
    except Exception as exc:  # yfinance can raise transport or parsing exceptions.
        df = pd.DataFrame(columns=RAW_COLUMNS)
        status = "FETCH_ERROR"
        error = str(exc)

    metadata = {
        "ticker": ticker,
        "source": "Yahoo Finance",
        "fetch_timestamp_utc": fetched_at,
        "period": period,
        "interval": interval,
        "rows": int(len(df)),
        "start_date": None if df.empty else str(df["date"].iloc[0]),
        "end_date": None if df.empty else str(df["date"].iloc[-1]),
        "status": status,
        "error": error,
    }
    return FetchResult(ticker=ticker, data=df, metadata=metadata)


def save_raw_data(df: pd.DataFrame, ticker: str, data_dir: Path) -> Path | None:
    if df.empty:
        return None
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{ticker}.csv"
    df.to_csv(path, index=False)
    return path
