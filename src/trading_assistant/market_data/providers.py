from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import yfinance as yf

from trading_assistant.market_data.base import (
    MarketDataProvider,
    MarketDataResult,
    ProviderRequestError,
    RateLimitError,
    build_result_metadata,
    normalize_ohlcv_frame,
    utc_now_iso,
)
from trading_assistant.market_data.retry import run_with_retry


class YahooFinanceProvider:
    name = "yahoo"
    source_name = "Yahoo Finance"

    def __init__(self, cache_dir: Path | None = None, max_attempts: int = 2) -> None:
        self.cache_dir = cache_dir
        self.max_attempts = max_attempts

    def is_available(self) -> bool:
        return True

    def get_historical(self, ticker: str, period: str, interval: str) -> MarketDataResult:
        fetched_at = utc_now_iso()
        started = perf_counter()

        def fetch() -> pd.DataFrame:
            # Use Yahoo's chart endpoint directly. yfinance may attempt to open
            # its timezone/cookie SQLite cache in a read-only runtime, causing
            # an otherwise healthy request to fail with "unable to open database file".
            if period not in {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}:
                raise ProviderRequestError(f"Unsupported Yahoo period: {period}", code="INVALID_PERIOD", retryable=False)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={period}&interval={interval}&events=history"
            try:
                with urlopen(Request(url, headers={"User-Agent": "IDX-Trading-Assistant/1.0"}), timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code == 429:
                    raise RateLimitError() from exc
                raise ProviderRequestError(f"Yahoo HTTP {exc.code}", code=f"HTTP_{exc.code}", retryable=exc.code >= 500) from exc
            except (URLError, TimeoutError, OSError) as exc:
                raise ProviderRequestError(str(exc), code="NETWORK_ERROR", retryable=True) from exc
            result = payload.get("chart", {}).get("result") if isinstance(payload, dict) else None
            if not result:
                error = payload.get("chart", {}).get("error") if isinstance(payload, dict) else None
                raise ProviderRequestError(str(error or "Empty Yahoo response"), code="INVALID_RESPONSE", retryable=False)
            item = result[0]
            timestamps = item.get("timestamp") or []
            quote = (item.get("indicators", {}).get("quote") or [{}])[0]
            adj = (item.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose", [])
            return pd.DataFrame({
                "date": pd.to_datetime(timestamps, unit="s", utc=True),
                "open": quote.get("open", []), "high": quote.get("high", []),
                "low": quote.get("low", []), "close": quote.get("close", []),
                "adj_close": adj, "volume": quote.get("volume", []),
            })

        try:
            raw, attempts = run_with_retry(fetch, max_attempts=self.max_attempts)
            frame = normalize_ohlcv_frame(raw, ticker=ticker, source=self.source_name,
                                          interval=interval, retrieved_at=fetched_at,
                                          is_delayed=True, delay_seconds=None)
            status = "FETCHED" if not frame.empty else "DATA_MISSING"
            error = error_code = None
        except ProviderRequestError as exc:
            frame, attempts = pd.DataFrame(), self.max_attempts
            status, error, error_code = "FETCH_ERROR", str(exc), exc.code
        metadata = build_result_metadata(ticker=ticker, provider=self.name, source=self.source_name,
                                         frame=frame, period=period, interval=interval,
                                         status=status, fetched_at=fetched_at,
                                         latency_class="DELAYED_HISTORICAL", is_delayed=True,
                                         delay_seconds=None, attempts=attempts, error=error,
                                         error_code=error_code)
        metadata["latency_ms"] = round((perf_counter() - started) * 1000, 2)
        return MarketDataResult(ticker, frame, metadata)


class EODHDProvider:
    name = "eodhd"
    source_name = "EODHD"

    def __init__(self, token: str | None = None, max_attempts: int = 2) -> None:
        self.token = token or os.getenv("EODHD_API_TOKEN")
        self.max_attempts = max_attempts

    def is_available(self) -> bool:
        return bool(self.token)

    def get_historical(self, ticker: str, period: str, interval: str) -> MarketDataResult:
        if not self.token:
            raise ProviderRequestError("EODHD token is not configured", code="NOT_CONFIGURED", retryable=False)
        if interval not in {"1d", "1wk", "1mo"}:
            raise ProviderRequestError("EODHD adapter currently supports daily-or-slower data only",
                                       code="UNSUPPORTED_INTERVAL", retryable=False)
        fetched_at = utc_now_iso()
        symbol = ticker if "." in ticker else f"{ticker}.JK"
        url = f"https://eodhd.com/api/eod/{symbol}?api_token={self.token}&fmt=json&period=d"

        def fetch() -> list[dict]:
            try:
                with urlopen(Request(url, headers={"User-Agent": "IDX-Trading-Assistant/1.0"}), timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code == 429:
                    raise RateLimitError() from exc
                raise ProviderRequestError(f"EODHD HTTP {exc.code}", code=f"HTTP_{exc.code}", retryable=exc.code >= 500) from exc
            except (URLError, TimeoutError, OSError) as exc:
                raise ProviderRequestError(str(exc), code="NETWORK_ERROR", retryable=True) from exc
            if not isinstance(payload, list):
                raise ProviderRequestError("Unexpected EODHD response", code="INVALID_RESPONSE", retryable=False)
            return payload

        try:
            payload, attempts = run_with_retry(fetch, max_attempts=self.max_attempts)
            frame = normalize_ohlcv_frame(pd.DataFrame(payload), ticker=ticker, source=self.source_name,
                                          interval=interval, retrieved_at=fetched_at,
                                          is_delayed=True, delay_seconds=10800)
            status = "FETCHED" if not frame.empty else "DATA_MISSING"
            error = error_code = None
        except ProviderRequestError as exc:
            frame, attempts = pd.DataFrame(), self.max_attempts
            status, error, error_code = "FETCH_ERROR", str(exc), exc.code
        return MarketDataResult(ticker, frame, build_result_metadata(
            ticker=ticker, provider=self.name, source=self.source_name, frame=frame,
            period=period, interval=interval, status=status, fetched_at=fetched_at,
            latency_class="DELAYED_HISTORICAL", is_delayed=True, delay_seconds=10800,
            attempts=attempts, error=error, error_code=error_code))


class IDXLicensedFileProvider:
    name = "idx_licensed"
    source_name = "IDX Licensed File Drop"

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or (Path(os.getenv("IDX_LICENSED_DATA_DIR")) if os.getenv("IDX_LICENSED_DATA_DIR") else None)

    def is_available(self) -> bool:
        return bool(self.data_dir and self.data_dir.is_dir())

    def get_historical(self, ticker: str, period: str, interval: str) -> MarketDataResult:
        if not self.is_available():
            raise ProviderRequestError("IDX licensed file directory is not configured", code="NOT_CONFIGURED", retryable=False)
        local_symbol = "IHSG" if ticker == "^JKSE" else ticker
        candidates = [self.data_dir / f"{local_symbol}.csv", self.data_dir / f"{local_symbol.replace('.JK', '')}.csv"]
        path = next((candidate for candidate in candidates if candidate.is_file()), None)
        if path is None:
            raise ProviderRequestError(f"No licensed file for {ticker}", code="DATA_MISSING", retryable=False)
        try:
            raw = pd.read_csv(path)
        except (OSError, ValueError) as exc:
            raise ProviderRequestError(str(exc), code="FILE_ERROR", retryable=False) from exc
        fetched_at = utc_now_iso()
        frame = normalize_ohlcv_frame(raw, ticker=ticker, source=self.source_name, interval=interval,
                                      retrieved_at=fetched_at, is_delayed=True, delay_seconds=None)
        return MarketDataResult(ticker, frame, build_result_metadata(
            ticker=ticker, provider=self.name, source=self.source_name, frame=frame,
            period=period, interval=interval, status="FETCHED" if not frame.empty else "DATA_MISSING",
            fetched_at=fetched_at, latency_class="VENDOR_DROP", is_delayed=True,
            delay_seconds=None))
