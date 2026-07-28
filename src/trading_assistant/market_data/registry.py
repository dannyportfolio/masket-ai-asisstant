from __future__ import annotations

import logging
import pandas as pd
from pathlib import Path

from trading_assistant.market_data.base import MarketDataResult, ProviderRequestError
from trading_assistant.market_data.cache import MarketDataCache
from trading_assistant.market_data.providers import EODHDProvider, IDXLicensedFileProvider, YahooFinanceProvider

logger = logging.getLogger(__name__)
DEFAULT_PROVIDER_PRIORITY = ("idx_licensed", "eodhd", "yahoo")


class ProviderRegistry:
    def __init__(self, providers: dict, priority: tuple[str, ...], cache: MarketDataCache | None = None) -> None:
        self.providers, self.priority, self.cache = providers, priority, cache

    def fetch(self, ticker: str, period: str, interval: str) -> MarketDataResult:
        errors = []
        for name in self.priority:
            provider = self.providers.get(name)
            if provider is None or not provider.is_available():
                continue
            try:
                result = provider.get_historical(ticker, period, interval)
            except ProviderRequestError as exc:
                errors.append(f"{name}:{exc.code}")
                logger.warning("market data provider failed", extra={"provider": name, "ticker": ticker, "code": exc.code})
                continue
            if not result.data.empty:
                if self.cache:
                    self.cache.save(name, ticker, period, interval, result)
                result.metadata["provider_attempt_log"] = errors
                return result
            errors.append(f"{name}:DATA_MISSING")
        if self.cache:
            for name in self.priority:
                cached = self.cache.load(name, ticker, period, interval)
                if cached:
                    cached.metadata["provider_attempt_log"] = errors
                    return cached
        return MarketDataResult(ticker, pd.DataFrame(), {
            "ticker": ticker, "source": None, "provider": None, "exchange": "IDX",
            "fetch_timestamp_utc": None, "retrieved_at": None, "period": period, "interval": interval,
            "rows": 0, "start_date": None, "end_date": None, "latency_class": "UNAVAILABLE",
            "is_delayed": True, "delay_seconds": None, "provider_attempts": len(errors),
            "status": "FETCH_ERROR", "error": ";".join(errors) or "No provider available",
            "provider_attempt_log": errors,
        })


def build_default_registry(data_dir: Path, provider_priority=None, idx_data_dir=None,
                           eodhd_token=None, cross_validate=True) -> ProviderRegistry:
    del cross_validate
    priority = tuple(provider_priority or DEFAULT_PROVIDER_PRIORITY)
    cache = MarketDataCache(data_dir / "cache" / "market_data")
    return ProviderRegistry({
        "idx_licensed": IDXLicensedFileProvider(idx_data_dir),
        "eodhd": EODHDProvider(eodhd_token),
        "yahoo": YahooFinanceProvider(data_dir / "cache" / "yfinance"),
    }, priority, cache)
