from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trading_assistant.indicators.cmf import add_cmf
from trading_assistant.indicators.moving_average import add_moving_averages
from trading_assistant.indicators.vpa import add_basic_vpa


IHSG_TICKER = "^JKSE"


@dataclass(frozen=True)
class MarketRegimeResult:
    ticker: str
    status: str
    ihsg_regime: str
    ihsg_trend_score: int
    ihsg_cmf_20: float | None
    ihsg_cmf_60: float | None
    ihsg_vpa_signal: str
    macro_permission: str
    macro_reason: str
    as_of_date: str | None
    evidence: dict

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "status": self.status,
            "ihsg_regime": self.ihsg_regime,
            "ihsg_trend_score": self.ihsg_trend_score,
            "ihsg_cmf_20": self.ihsg_cmf_20,
            "ihsg_cmf_60": self.ihsg_cmf_60,
            "ihsg_vpa_signal": self.ihsg_vpa_signal,
            "macro_permission": self.macro_permission,
            "macro_reason": self.macro_reason,
            "as_of_date": self.as_of_date,
            "evidence": self.evidence,
        }


def add_market_structure(df: pd.DataFrame, swing_window: int = 20) -> pd.DataFrame:
    result = df.copy()
    high = pd.to_numeric(result["high"], errors="coerce")
    low = pd.to_numeric(result["low"], errors="coerce")
    result["rolling_high_20"] = high.rolling(swing_window, min_periods=max(5, swing_window // 4)).max()
    result["rolling_low_20"] = low.rolling(swing_window, min_periods=max(5, swing_window // 4)).min()
    result["prev_rolling_high_20"] = result["rolling_high_20"].shift(swing_window)
    result["prev_rolling_low_20"] = result["rolling_low_20"].shift(swing_window)
    result["higher_high"] = result["rolling_high_20"] > result["prev_rolling_high_20"]
    result["higher_low"] = result["rolling_low_20"] > result["prev_rolling_low_20"]
    result["lower_high"] = result["rolling_high_20"] < result["prev_rolling_high_20"]
    result["lower_low"] = result["rolling_low_20"] < result["prev_rolling_low_20"]
    return result


def prepare_ihsg_frame(raw_df: pd.DataFrame) -> pd.DataFrame:
    result = add_basic_vpa(add_cmf(raw_df, windows=(20, 60)))
    result = add_moving_averages(result, windows=(20, 50, 200))
    result["ma50_slope_10"] = result["ma_50"] - result["ma_50"].shift(10)
    result["cmf20_delta_10"] = result["cmf_20"] - result["cmf_20"].shift(10)
    result["cmf60_delta_10"] = result["cmf_60"] - result["cmf_60"].shift(10)
    return add_market_structure(result)


def detect_ihsg_vpa_signal(latest: pd.Series) -> str:
    if bool(latest.get("effort_no_result_up", False)) and bool(latest.get("high_volume", False)):
        return "DISTRIBUTION_PRESSURE"
    if bool(latest.get("effort_no_result_down", False)) and bool(latest.get("high_volume", False)):
        return "ACCUMULATION_PRESSURE"
    if bool(latest.get("wide_spread_down_bar", False)) and bool(latest.get("high_volume", False)):
        return "SELLING_CLIMAX_CANDIDATE"
    if bool(latest.get("wide_spread_up_bar", False)) and bool(latest.get("high_volume", False)):
        return "BUYING_CLIMAX_CANDIDATE"
    if bool(latest.get("narrow_spread_high_volume", False)):
        return "ABSORPTION_OR_CHURN"
    if bool(latest.get("wide_spread_up_bar", False)) and bool(latest.get("close_near_high", False)):
        return "SIGN_OF_STRENGTH_CANDIDATE"
    if bool(latest.get("wide_spread_down_bar", False)) and bool(latest.get("close_near_low", False)):
        return "SIGN_OF_WEAKNESS_CANDIDATE"
    return "NO_CLEAR_VPA_SIGNAL"


def _clean_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(parsed) or np.isinf(parsed):
        return None
    return parsed


def screen_ihsg_regime(raw_df: pd.DataFrame, quality_status: str = "OK") -> tuple[MarketRegimeResult, pd.DataFrame]:
    if raw_df.empty or quality_status in {"DATA_MISSING", "FETCH_ERROR"}:
        result = MarketRegimeResult(
            ticker=IHSG_TICKER,
            status="DATA_MISSING",
            ihsg_regime="DATA_MISSING",
            ihsg_trend_score=0,
            ihsg_cmf_20=None,
            ihsg_cmf_60=None,
            ihsg_vpa_signal="DATA_MISSING",
            macro_permission="MACRO_UNVERIFIED",
            macro_reason="IHSG Yahoo Finance data is unavailable, so individual-stock signals must be macro-unverified.",
            as_of_date=None,
            evidence={},
        )
        return result, raw_df

    prepared = prepare_ihsg_frame(raw_df)
    latest = prepared.dropna(subset=["close"]).iloc[-1]
    score = 0
    reasons: list[str] = []

    close = _clean_float(latest.get("close"))
    ma20 = _clean_float(latest.get("ma_20"))
    ma50 = _clean_float(latest.get("ma_50"))
    ma200 = _clean_float(latest.get("ma_200"))
    ma50_slope = _clean_float(latest.get("ma50_slope_10"))
    cmf20 = _clean_float(latest.get("cmf_20"))
    cmf60 = _clean_float(latest.get("cmf_60"))
    cmf20_delta = _clean_float(latest.get("cmf20_delta_10"))

    if close is not None and ma50 is not None:
        if close > ma50:
            score += 25
            reasons.append("close_above_ma50")
        else:
            score -= 25
            reasons.append("close_below_ma50")
    if ma20 is not None and ma50 is not None:
        if ma20 > ma50:
            score += 20
            reasons.append("ma20_above_ma50")
        else:
            score -= 20
            reasons.append("ma20_below_ma50")
    if ma50_slope is not None:
        if ma50_slope > 0:
            score += 15
            reasons.append("ma50_rising")
        elif ma50_slope < 0:
            score -= 15
            reasons.append("ma50_falling")
    if ma50 is not None and ma200 is not None:
        if ma50 > ma200:
            score += 10
            reasons.append("ma50_above_ma200")
        else:
            score -= 10
            reasons.append("ma50_below_ma200")

    if bool(latest.get("higher_high", False)) and bool(latest.get("higher_low", False)):
        score += 20
        structure = "UPTREND"
        reasons.append("higher_high_higher_low")
    elif bool(latest.get("lower_high", False)) and bool(latest.get("lower_low", False)):
        score -= 20
        structure = "DOWNTREND"
        reasons.append("lower_high_lower_low")
    else:
        structure = "SIDEWAYS"
        reasons.append("market_structure_unclear")

    if cmf20 is not None and cmf60 is not None:
        if cmf20 > 0 and cmf60 > 0:
            score += 10
            reasons.append("cmf_positive")
        elif cmf20 < 0 and cmf60 < 0:
            score -= 10
            reasons.append("cmf_negative")
    if cmf20_delta is not None:
        if cmf20_delta > 0:
            score += 5
            reasons.append("cmf20_strengthening")
        elif cmf20_delta < 0:
            score -= 5
            reasons.append("cmf20_weakening")

    vpa_signal = detect_ihsg_vpa_signal(latest)
    if vpa_signal in {"ACCUMULATION_PRESSURE", "SIGN_OF_STRENGTH_CANDIDATE"}:
        score += 10
        reasons.append(vpa_signal.lower())
    elif vpa_signal in {"DISTRIBUTION_PRESSURE", "SIGN_OF_WEAKNESS_CANDIDATE"}:
        score -= 10
        reasons.append(vpa_signal.lower())

    score = int(max(-100, min(100, score)))

    if abs(score) < 25:
        regime = "SIDEWAYS" if structure == "SIDEWAYS" else "VOLATILE_UNCLEAR"
    elif score >= 55:
        regime = "BULLISH"
    elif score <= -55:
        regime = "BEARISH"
    elif structure == "SIDEWAYS":
        regime = "SIDEWAYS"
    else:
        regime = "VOLATILE_UNCLEAR"

    if regime == "BULLISH":
        permission = "LONG_ALLOWED"
    elif regime == "BEARISH":
        permission = "SHORT_OR_EXIT_ALLOWED"
    elif regime == "SIDEWAYS":
        permission = "LONG_RESTRICTED"
    elif regime == "VOLATILE_UNCLEAR":
        permission = "WAIT_ONLY"
    else:
        permission = "MACRO_UNVERIFIED"

    if vpa_signal == "DISTRIBUTION_PRESSURE" and permission == "LONG_ALLOWED":
        permission = "LONG_RESTRICTED"
        reasons.append("distribution_pressure_restricts_longs")

    result = MarketRegimeResult(
        ticker=IHSG_TICKER,
        status=quality_status,
        ihsg_regime=regime,
        ihsg_trend_score=score,
        ihsg_cmf_20=cmf20,
        ihsg_cmf_60=cmf60,
        ihsg_vpa_signal=vpa_signal,
        macro_permission=permission,
        macro_reason=", ".join(reasons),
        as_of_date=str(latest.get("date")),
        evidence={
            "close": close,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "ma50_slope_10": ma50_slope,
            "market_structure": structure,
            "cmf20_delta_10": cmf20_delta,
        },
    )
    return result, prepared
