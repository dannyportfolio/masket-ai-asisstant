from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import pandas as pd


NORMALIZED_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "ticker",
    "exchange",
    "timeframe",
    "source",
    "exchange_timestamp",
    "retrieved_at",
    "data_quality",
    "is_delayed",
    "delay_seconds",
]


@dataclass(frozen=True)
class MarketDataResult:
    ticker: str
    data: pd.DataFrame
    metadata: dict


class ProviderRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "PROVIDER_ERROR",
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class RateLimitError(ProviderRequestError):
    def __init__(self, message: str = "Provider rate limit reached") -> None:
        super().__init__(message, code="RATE_LIMITED", retryable=True)


class MarketDataProvider(Protocol):
    name: str
    source_name: str

    def is_available(self) -> bool:
        ...

    def get_historical(
        self,
        ticker: str,
        period: str,
        interval: str,
    ) -> MarketDataResult:
        ...


def empty_market_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=NORMALIZED_COLUMNS)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_ohlcv_frame(
    frame: pd.DataFrame,
    *,
    ticker: str,
    source: str,
    interval: str,
    retrieved_at: str | None = None,
    is_delayed: bool,
    delay_seconds: int | None,
) -> pd.DataFrame:
    if frame.empty:
        return empty_market_frame()

    result = frame.copy()
    aliases = {
        "Date": "date",
        "Datetime": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Adjusted_close": "adj_close",
        "adjusted_close": "adj_close",
        "Volume": "volume",
    }
    result = result.rename(columns=aliases)
    if "adj_close" not in result.columns:
        result["adj_close"] = pd.NA

    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        if column not in result.columns:
            result[column] = pd.NA
        result[column] = pd.to_numeric(result[column], errors="coerce")

    parsed_dates = pd.to_datetime(result.get("date"), errors="coerce")
    if interval in {"1d", "1wk", "1mo"}:
        result["date"] = parsed_dates.dt.strftime("%Y-%m-%d").astype("string")
    else:
        result["date"] = parsed_dates.astype("string")

    try:
        if parsed_dates.dt.tz is None:
            exchange_dates = parsed_dates.dt.tz_localize(
                "Asia/Jakarta",
                ambiguous="NaT",
                nonexistent="shift_forward",
            )
        else:
            exchange_dates = parsed_dates.dt.tz_convert("Asia/Jakarta")
        result["exchange_timestamp"] = exchange_dates.map(
            lambda value: value.isoformat() if pd.notna(value) else None
        )
    except (AttributeError, TypeError, ValueError):
        result["exchange_timestamp"] = result["date"]

    result["ticker"] = ticker
    result["exchange"] = "IDX"
    result["timeframe"] = interval
    result["source"] = source
    result["retrieved_at"] = retrieved_at or utc_now_iso()
    result["data_quality"] = "UNVALIDATED"
    result["is_delayed"] = bool(is_delayed)
    result["delay_seconds"] = delay_seconds
    return result[NORMALIZED_COLUMNS].sort_values("date").reset_index(drop=True)


def build_result_metadata(
    *,
    ticker: str,
    provider: str,
    source: str,
    frame: pd.DataFrame,
    period: str,
    interval: str,
    status: str,
    fetched_at: str,
    latency_class: str,
    is_delayed: bool,
    delay_seconds: int | None,
    attempts: int = 1,
    error: str | None = None,
    error_code: str | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "provider": provider,
        "source": source,
        "exchange": "IDX",
        "fetch_timestamp_utc": fetched_at,
        "retrieved_at": fetched_at,
        "period": period,
        "interval": interval,
        "rows": int(len(frame)),
        "start_date": None if frame.empty else str(frame["date"].iloc[0]),
        "end_date": None if frame.empty else str(frame["date"].iloc[-1]),
        "status": status,
        "latency_class": latency_class,
        "is_delayed": is_delayed,
        "delay_seconds": delay_seconds,
        "provider_attempts": attempts,
        "error": error,
        "error_code": error_code,
    }
