from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re

import pandas as pd

from trading_assistant.market_data.base import MarketDataResult, empty_market_frame


class MarketDataCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _safe(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)

    def _paths(
        self,
        provider: str,
        ticker: str,
        period: str,
        interval: str,
    ) -> tuple[Path, Path]:
        provider_dir = self.root / self._safe(provider)
        stem = "_".join(self._safe(value) for value in (ticker, period, interval))
        return provider_dir / f"{stem}.csv", provider_dir / f"{stem}.metadata.json"

    def save(
        self,
        provider: str,
        ticker: str,
        period: str,
        interval: str,
        result: MarketDataResult,
    ) -> None:
        if result.data.empty:
            return
        data_path, metadata_path = self._paths(provider, ticker, period, interval)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        result.data.to_csv(data_path, index=False)
        payload = dict(result.metadata)
        payload["cache_saved_at_utc"] = datetime.now(timezone.utc).isoformat()
        metadata_path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )

    def load(
        self,
        provider: str,
        ticker: str,
        period: str,
        interval: str,
    ) -> MarketDataResult | None:
        data_path, metadata_path = self._paths(provider, ticker, period, interval)
        if not data_path.is_file() or not metadata_path.is_file():
            return None
        try:
            frame = pd.read_csv(data_path)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if frame.empty:
            return MarketDataResult(ticker, empty_market_frame(), metadata)

        saved_at = metadata.get("cache_saved_at_utc")
        age_seconds: int | None = None
        if saved_at:
            try:
                saved = datetime.fromisoformat(str(saved_at))
                if saved.tzinfo is None:
                    saved = saved.replace(tzinfo=timezone.utc)
                age_seconds = max(
                    0,
                    int((datetime.now(timezone.utc) - saved).total_seconds()),
                )
            except ValueError:
                age_seconds = None

        stale = frame.copy()
        stale["data_quality"] = "STALE_CACHE"
        stale["is_delayed"] = True
        metadata.update(
            {
                "status": "STALE_CACHE_FALLBACK",
                "cache_fallback": True,
                "cache_age_seconds": age_seconds,
                "rows": int(len(stale)),
                "error": None,
                "error_code": None,
            }
        )
        return MarketDataResult(ticker=ticker, data=stale, metadata=metadata)
