from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EngineResult:
    frame: pd.DataFrame
    requested_engine: str
    used_engine: str | None
    status: str
    source_revision: str | None = None
    added_columns: tuple[str, ...] = ()
    error: str | None = None

    def metadata(self) -> dict:
        return {
            "analytics_engine_requested": self.requested_engine,
            "analytics_engine_used": self.used_engine,
            "analytics_engine_status": self.status,
            "analytics_engine_revision": self.source_revision,
            "analytics_engine_added_columns": len(self.added_columns),
            "analytics_engine_error": self.error,
        }
