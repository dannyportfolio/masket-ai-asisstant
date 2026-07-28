from __future__ import annotations

from functools import lru_cache
import hashlib
import importlib.util
from pathlib import Path
from types import ModuleType

import pandas as pd

from trading_assistant.engines.base import EngineResult
from trading_assistant.indicators.cmf import add_cmf
from trading_assistant.indicators.vpa import add_basic_vpa


FINCEPT_REVISION = "fec23dc78c935e001394ea8df3f820eddd0823a0"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FINCEPT_SCRIPT = (
    PROJECT_ROOT
    / "vendor"
    / "FinceptTerminal"
    / "fincept-qt"
    / "scripts"
    / "compute_technicals.py"
)
REQUIRED_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
MIN_FINCEPT_BARS = 60
DISABLED_MA_PREFIXES = ("ma_", "sma_", "ema_", "wma_")
DISABLED_MA_COLUMNS = {"kama", "bb_mavg", "kc_mavg"}


class FinceptEngineError(RuntimeError):
    """Raised when the vendored Fincept technical engine cannot run safely."""


@lru_cache(maxsize=4)
def _load_fincept_module(script_path: str) -> ModuleType:
    path = Path(script_path)
    if not path.is_file():
        raise FinceptEngineError(
            f"Fincept technical engine is missing at {path}. "
            "Initialize the vendor/FinceptTerminal submodule."
        )

    module_suffix = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(
        f"_d_markets_fincept_technicals_{module_suffix}",
        path,
    )
    if spec is None or spec.loader is None:
        raise FinceptEngineError(f"Unable to load Fincept module spec from {path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ModuleNotFoundError as exc:
        if exc.name == "ta":
            raise FinceptEngineError(
                "Fincept requires ta==0.11.0; install requirements.txt."
            ) from exc
        raise FinceptEngineError(f"Fincept dependency is unavailable: {exc.name}") from exc
    return module


class FinceptTechnicalEngine:
    name = "fincept"

    def __init__(self, script_path: Path | None = None) -> None:
        self.script_path = (script_path or DEFAULT_FINCEPT_SCRIPT).resolve()

    def enrich(self, frame: pd.DataFrame) -> EngineResult:
        missing = [column for column in REQUIRED_OHLCV_COLUMNS if column not in frame.columns]
        if missing:
            raise FinceptEngineError(
                "Fincept input is missing required columns: " + ", ".join(missing)
            )
        if len(frame) < MIN_FINCEPT_BARS:
            raise FinceptEngineError(
                f"Fincept requires at least {MIN_FINCEPT_BARS} bars for its full "
                f"indicator set; received {len(frame)}"
            )

        module = _load_fincept_module(str(self.script_path))
        original_columns = set(frame.columns)
        result = frame.copy()

        try:
            result = module.calculate_all_trend_indicators(result)
            result = module.calculate_all_momentum_indicators(result)
            result = module.calculate_all_volatility_indicators(result)
            result = module.calculate_all_volume_indicators(result)
            result = module.calculate_all_others_indicators(result)
        except Exception as exc:
            raise FinceptEngineError(
                f"Fincept technical calculation failed: {type(exc).__name__}: {exc}"
            ) from exc

        if len(result) != len(frame) or not result.index.equals(frame.index):
            raise FinceptEngineError("Fincept changed the OHLCV row alignment")

        required_engine_columns = {
            "cmf": "cmf_20",
            "atr": "atr_14",
        }
        missing_outputs = [
            source for source in required_engine_columns if source not in result.columns
        ]
        if missing_outputs:
            raise FinceptEngineError(
                "Fincept did not return required indicators: " + ", ".join(missing_outputs)
            )

        # Preserve the established D-Markets contract while sourcing overlapping
        # non-MA metrics from Fincept. IDX-specific CMF windows and VPA remain local.
        result = add_cmf(result, windows=(10, 60))
        result = add_basic_vpa(result)
        for source, target in required_engine_columns.items():
            result[target] = result[source]
        result = result.drop(
            columns=[
                column for column in result.columns
                if column.lower().startswith(DISABLED_MA_PREFIXES)
                or column.lower() in DISABLED_MA_COLUMNS
            ],
            errors="ignore",
        )

        added_columns = tuple(column for column in result.columns if column not in original_columns)
        return EngineResult(
            frame=result,
            requested_engine=self.name,
            used_engine=self.name,
            status="OK",
            source_revision=FINCEPT_REVISION,
            added_columns=added_columns,
        )
