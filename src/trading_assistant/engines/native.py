from __future__ import annotations

import pandas as pd

from trading_assistant.engines.base import EngineResult
from trading_assistant.indicators.atr import add_atr
from trading_assistant.indicators.cmf import add_cmf
from trading_assistant.indicators.vpa import add_basic_vpa
from trading_assistant.indicators.volume import add_volume_intelligence


class NativeTechnicalEngine:
    name = "native"

    def enrich(self, frame: pd.DataFrame, requested_engine: str = "native") -> EngineResult:
        original_columns = set(frame.columns)
        result = add_volume_intelligence(add_atr(add_basic_vpa(add_cmf(frame))))
        added_columns = tuple(column for column in result.columns if column not in original_columns)
        return EngineResult(
            frame=result,
            requested_engine=requested_engine,
            used_engine=self.name,
            status="OK",
            added_columns=added_columns,
        )
