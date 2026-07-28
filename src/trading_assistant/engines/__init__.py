from __future__ import annotations

from pathlib import Path

import pandas as pd

from trading_assistant.engines.base import EngineResult
from trading_assistant.engines.fincept import FINCEPT_REVISION, FinceptTechnicalEngine
from trading_assistant.engines.native import NativeTechnicalEngine


ANALYTICS_ENGINES = ("fincept", "native")


def enrich_market_frame(
    frame: pd.DataFrame,
    requested_engine: str = "fincept",
    *,
    fincept_script: Path | None = None,
) -> EngineResult:
    engine_name = requested_engine.strip().lower()
    if engine_name not in ANALYTICS_ENGINES:
        raise ValueError(
            f"Unknown analytics engine {requested_engine!r}; "
            f"expected one of {', '.join(ANALYTICS_ENGINES)}"
        )

    if frame.empty:
        return EngineResult(
            frame=frame.copy(),
            requested_engine=engine_name,
            used_engine=None,
            status="NOT_RUN",
            source_revision=FINCEPT_REVISION if engine_name == "fincept" else None,
        )

    if engine_name == "native":
        return NativeTechnicalEngine().enrich(frame)

    try:
        return FinceptTechnicalEngine(script_path=fincept_script).enrich(frame)
    except Exception as exc:
        fallback = NativeTechnicalEngine().enrich(frame, requested_engine=engine_name)
        return EngineResult(
            frame=fallback.frame,
            requested_engine=engine_name,
            used_engine=fallback.used_engine,
            status="FALLBACK_NATIVE",
            source_revision=FINCEPT_REVISION,
            added_columns=fallback.added_columns,
            error=f"{type(exc).__name__}: {exc}",
        )


__all__ = [
    "ANALYTICS_ENGINES",
    "EngineResult",
    "FINCEPT_REVISION",
    "FinceptTechnicalEngine",
    "NativeTechnicalEngine",
    "enrich_market_frame",
]
