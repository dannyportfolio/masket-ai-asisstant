from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


MIN_CONFIDENCE = 60
MIN_RR_TARGET_1 = 1.5
MIN_RR_TARGET_2 = 2.0


@dataclass(frozen=True)
class TradeAnalysis:
    ticker: str
    analysis_date: str | None
    data_status: str
    ihsg_context: dict
    wyckoff_vpa: dict
    cmf: dict
    saturation_index: dict
    relative_strength: dict
    trade_plan: dict

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "analysis_date": self.analysis_date,
            "data_status": self.data_status,
            "ihsg_context": self.ihsg_context,
            "wyckoff_vpa": self.wyckoff_vpa,
            "cmf": self.cmf,
            "saturation_index": self.saturation_index,
            "relative_strength": self.relative_strength,
            "trade_plan": self.trade_plan,
        }


def add_atr(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    result = df.copy()
    high = pd.to_numeric(result["high"], errors="coerce")
    low = pd.to_numeric(result["low"], errors="coerce")
    close = pd.to_numeric(result["close"], errors="coerce")
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    result[f"atr_{window}"] = true_range.rolling(window, min_periods=window).mean()
    return result


def _clean_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(parsed) or np.isinf(parsed):
        return None
    return parsed


def _round_price(value: float | None) -> float | None:
    if value is None:
        return None
    if value >= 1000:
        return round(value / 5) * 5
    return round(value, 2)


def calculate_relative_strength(stock_df: pd.DataFrame, ihsg_df: pd.DataFrame) -> dict:
    if stock_df.empty or ihsg_df.empty:
        return {
            "relative_strength_20": None,
            "relative_strength_60": None,
            "relative_strength_status": "MACRO_UNVERIFIED",
        }

    stock = stock_df[["date", "close"]].copy()
    ihsg = ihsg_df[["date", "close"]].copy()
    stock["date"] = pd.to_datetime(stock["date"], errors="coerce")
    ihsg["date"] = pd.to_datetime(ihsg["date"], errors="coerce")
    merged = stock.merge(ihsg, on="date", how="inner", suffixes=("_stock", "_ihsg")).dropna()
    if len(merged) < 61:
        return {
            "relative_strength_20": None,
            "relative_strength_60": None,
            "relative_strength_status": "DATA_INSUFFICIENT",
        }

    stock_close = pd.to_numeric(merged["close_stock"], errors="coerce")
    ihsg_close = pd.to_numeric(merged["close_ihsg"], errors="coerce")
    stock_ret_20 = stock_close.iloc[-1] / stock_close.iloc[-21] - 1
    ihsg_ret_20 = ihsg_close.iloc[-1] / ihsg_close.iloc[-21] - 1
    stock_ret_60 = stock_close.iloc[-1] / stock_close.iloc[-61] - 1
    ihsg_ret_60 = ihsg_close.iloc[-1] / ihsg_close.iloc[-61] - 1
    rs20 = float(stock_ret_20 - ihsg_ret_20)
    rs60 = float(stock_ret_60 - ihsg_ret_60)

    if rs20 > 0.03 and rs60 > 0.05:
        status = "OUTPERFORMING_IHSG"
    elif rs20 < -0.03 and rs60 < -0.05:
        status = "UNDERPERFORMING_IHSG"
    else:
        status = "INLINE_WITH_IHSG"

    return {
        "relative_strength_20": rs20,
        "relative_strength_60": rs60,
        "relative_strength_status": status,
    }


def _technical_levels(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]
    close = _clean_float(latest.get("close"))
    atr = _clean_float(latest.get("atr_14"))
    lookback = df.tail(80).copy()
    recent = df.tail(20).copy()

    if close is None or atr is None or atr <= 0 or len(lookback) < 30:
        return {
            "valid": False,
            "reason": "technical levels are not clear enough",
        }

    highs = pd.to_numeric(lookback["high"], errors="coerce")
    lows = pd.to_numeric(lookback["low"], errors="coerce")
    recent_lows = pd.to_numeric(recent["low"], errors="coerce")
    recent_highs = pd.to_numeric(recent["high"], errors="coerce")

    support = _clean_float(recent_lows.min())
    resistance = _clean_float(recent_highs.max())
    major_high = _clean_float(highs.max())
    major_low = _clean_float(lows.min())
    if support is None or resistance is None or major_high is None or major_low is None:
        return {
            "valid": False,
            "reason": "support or resistance is unavailable",
        }

    base_range = max(resistance - support, atr)
    return {
        "valid": True,
        "close": close,
        "atr": atr,
        "support": support,
        "resistance": resistance,
        "major_high": major_high,
        "major_low": major_low,
        "base_range": base_range,
    }


def _score_saturation(df: pd.DataFrame) -> tuple[int, int, list[str], str, str]:
    latest = df.iloc[-1]
    cmf10 = _clean_float(latest.get("cmf_10")) or 0.0
    cmf20 = _clean_float(latest.get("cmf_20")) or 0.0
    cmf60 = _clean_float(latest.get("cmf_60")) or 0.0
    cmf20_prev = _clean_float(df["cmf_20"].iloc[-11]) if len(df) > 11 and "cmf_20" in df else None
    vwpa_pressure = _clean_float(latest.get("vwpa_pressure_20"))
    vwpa_signal = str(latest.get("vwpa_signal") or "")
    evidence: list[str] = []
    accumulation = 0
    distribution = 0

    if cmf20 > 0:
        accumulation += 20
        evidence.append("cmf20_positive")
    if cmf60 > 0:
        accumulation += 10
        evidence.append("cmf60_positive")
    if cmf20_prev is not None and cmf20 > cmf20_prev:
        accumulation += 15
        evidence.append("cmf20_strengthening")
    if bool(latest.get("effort_no_result_down", False)):
        accumulation += 20
        evidence.append("down_bar_high_volume_close_not_near_low")
    if bool(latest.get("narrow_spread_high_volume", False)):
        accumulation += 15
        distribution += 10
        evidence.append("narrow_spread_high_volume_absorption")
    if bool(latest.get("wide_spread_up_bar", False)) and bool(latest.get("close_near_high", False)):
        accumulation += 15
        evidence.append("sign_of_strength_candidate")
    if vwpa_signal == "VALUE_ACCUMULATION_PRESSURE" or (vwpa_pressure is not None and vwpa_pressure >= 0.2):
        accumulation += 20
        evidence.append("vwpa_value_accumulation_pressure")
    if cmf20 < 0:
        distribution += 20
        evidence.append("cmf20_negative")
    if cmf60 < 0:
        distribution += 10
        evidence.append("cmf60_negative")
    if cmf20_prev is not None and cmf20 < cmf20_prev:
        distribution += 15
        evidence.append("cmf20_weakening")
    if bool(latest.get("effort_no_result_up", False)):
        distribution += 20
        evidence.append("up_bar_high_volume_close_not_near_high")
    if bool(latest.get("wide_spread_down_bar", False)) and bool(latest.get("close_near_low", False)):
        distribution += 15
        evidence.append("sign_of_weakness_candidate")
    if vwpa_signal == "VALUE_DISTRIBUTION_PRESSURE" or (vwpa_pressure is not None and vwpa_pressure <= -0.2):
        distribution += 20
        evidence.append("vwpa_value_distribution_pressure")
    if vwpa_signal == "VALUE_ABSORPTION_OR_CHURN":
        accumulation += 10
        distribution += 10
        evidence.append("vwpa_value_absorption_or_churn")
    accumulation = int(min(100, accumulation))
    distribution = int(min(100, distribution))
    if accumulation >= 65 and accumulation > distribution:
        phase = "ACCUMULATION"
        main_signal = "ACCUMULATION_PRESSURE"
    elif distribution >= 65 and distribution > accumulation:
        phase = "DISTRIBUTION"
        main_signal = "DISTRIBUTION_PRESSURE"
    elif bool(latest.get("higher_high", False)) and bool(latest.get("higher_low", False)) and accumulation >= distribution:
        phase = "MARKUP"
        main_signal = "MARKUP_CONTINUATION_CANDIDATE"
    elif bool(latest.get("lower_high", False)) and bool(latest.get("lower_low", False)) and distribution > accumulation:
        phase = "MARKDOWN"
        main_signal = "MARKDOWN_RISK_CANDIDATE"
    else:
        phase = "NEUTRAL_UNCLEAR"
        main_signal = "NO_CLEAR_SIGNAL"
    return accumulation, distribution, evidence, phase, main_signal


def _no_trade_plan(action: str, reason: str, confidence: int = 0, macro_confirmation: str | None = None) -> dict:
    return {
        "trade_action": action,
        "entry_type": "NO_ENTRY",
        "entry_point": None,
        "target_point_1": None,
        "target_point_2": None,
        "cut_loss_point": None,
        "risk_per_share": None,
        "reward_to_target_1": None,
        "reward_to_target_2": None,
        "rr_target_1": None,
        "rr_target_2": None,
        "position_invalidated_if": reason,
        "trade_reason": reason,
        "macro_confirmation": macro_confirmation,
        "confidence": confidence,
    }


def build_trade_analysis(
    ticker: str,
    processed_df: pd.DataFrame,
    data_status: str,
    macro: dict,
    ihsg_processed_df: pd.DataFrame,
) -> TradeAnalysis:
    ihsg_context = {
        "ihsg_regime": macro.get("ihsg_regime"),
        "ihsg_trend_score": macro.get("ihsg_trend_score"),
        "macro_permission": macro.get("macro_permission"),
        "macro_reason": macro.get("macro_reason"),
    }
    if processed_df.empty or data_status in {"DATA_MISSING", "DATA_INSUFFICIENT", "FETCH_ERROR"}:
        plan = _no_trade_plan("DATA_INSUFFICIENT", "Data saham tidak cukup untuk trade plan.", macro_confirmation=macro.get("macro_permission"))
        return TradeAnalysis(ticker, None, data_status, ihsg_context, {}, {}, {}, {}, plan)

    df = processed_df.copy()
    if "atr_14" not in df.columns:
        df = add_atr(df)
    latest = df.iloc[-1]
    analysis_date = str(latest.get("date"))
    cmf = {
        "cmf_10": _clean_float(latest.get("cmf_10")),
        "cmf_20": _clean_float(latest.get("cmf_20")),
        "cmf_60": _clean_float(latest.get("cmf_60")),
    }
    accumulation, distribution, evidence, phase, main_signal = _score_saturation(df)
    rs = calculate_relative_strength(df, ihsg_processed_df)
    confidence = min(100, max(accumulation, distribution) + (15 if rs["relative_strength_status"] == "OUTPERFORMING_IHSG" else 0))

    wyckoff_vpa = {
        "phase": phase,
        "main_signal": main_signal,
        "evidence": evidence,
        "vwpa_signal": latest.get("vwpa_signal"),
        "vwpa_pressure_20": _clean_float(latest.get("vwpa_pressure_20")),
    }
    saturation = {
        "accumulation_saturation_index": accumulation,
        "distribution_saturation_index": distribution,
    }

    macro_permission = macro.get("macro_permission")
    if macro_permission == "MACRO_UNVERIFIED":
        plan = _no_trade_plan("WAIT", "IHSG tidak tersedia; sinyal harus MACRO_UNVERIFIED.", confidence, macro_permission)
    elif macro_permission == "WAIT_ONLY":
        plan = _no_trade_plan("WAIT", "IHSG volatile unclear; entry agresif tidak dibuat.", confidence, macro_permission)
    elif confidence < MIN_CONFIDENCE:
        action = "DISTRIBUTION_WARNING" if distribution >= 60 and distribution > accumulation else "WAIT"
        plan = _no_trade_plan(action, "Confidence belum memenuhi threshold trade plan.", confidence, macro_permission)
    else:
        levels = _technical_levels(df)
        if not levels["valid"]:
            plan = _no_trade_plan("WAIT", levels["reason"], confidence, macro_permission)
        else:
            plan = _build_plan_from_levels(levels, accumulation, distribution, phase, main_signal, rs, macro, confidence)

    return TradeAnalysis(
        ticker=ticker,
        analysis_date=analysis_date,
        data_status=data_status,
        ihsg_context=ihsg_context,
        wyckoff_vpa=wyckoff_vpa,
        cmf=cmf,
        saturation_index=saturation,
        relative_strength=rs,
        trade_plan=plan,
    )


def _build_plan_from_levels(
    levels: dict,
    accumulation: int,
    distribution: int,
    phase: str,
    main_signal: str,
    rs: dict,
    macro: dict,
    confidence: int,
) -> dict:
    close = levels["close"]
    atr = levels["atr"]
    support = levels["support"]
    resistance = levels["resistance"]
    major_high = levels["major_high"]
    base_range = levels["base_range"]
    macro_permission = macro.get("macro_permission")
    regime = macro.get("ihsg_regime")

    if distribution > accumulation and distribution >= 60:
        return _no_trade_plan(
            "DISTRIBUTION_WARNING" if phase != "MARKDOWN" else "EXIT_RISK",
            "Distribution/markdown risk lebih dominan daripada setup long.",
            confidence,
            macro_permission,
        )

    if accumulation < 60 and phase not in {"MARKUP", "ACCUMULATION"}:
        return _no_trade_plan("WAIT", "Tidak ada setup akumulasi atau markup yang cukup jelas.", confidence, macro_permission)

    entry_type = "BREAKOUT_ENTRY"
    entry = resistance + 0.2 * atr
    cut_loss = max(support - 0.5 * atr, 0)
    target1 = max(major_high, resistance + base_range)
    target2 = max(target1 + base_range, resistance + 2 * base_range)

    if close > resistance * 0.98 and rs["relative_strength_status"] == "OUTPERFORMING_IHSG":
        entry_type = "SUPPORT_RECLAIM_ENTRY"
        entry = close
        cut_loss = max(support - 0.5 * atr, 0)
    elif phase == "ACCUMULATION" and accumulation >= 70:
        entry_type = "PULLBACK_ENTRY"
        entry = max(support + 0.5 * atr, close)
        cut_loss = max(support - 0.5 * atr, 0)

    risk = entry - cut_loss
    reward1 = target1 - entry
    reward2 = target2 - entry
    if risk <= 0:
        return _no_trade_plan("WAIT", "Risk per share tidak valid karena cut loss tidak berada di bawah entry.", confidence, macro_permission)

    rr1 = reward1 / risk
    rr2 = reward2 / risk
    if rr1 < MIN_RR_TARGET_1:
        return _no_trade_plan("WAIT", f"RR target 1 hanya {rr1:.2f}, di bawah batas {MIN_RR_TARGET_1}.", confidence, macro_permission)

    trade_action = "BUY_SETUP"
    reason_bits = [main_signal.lower(), "technical_levels_clear", f"rr1_{rr1:.2f}"]
    if rr2 < MIN_RR_TARGET_2:
        reason_bits.append("target2_upside_less_attractive")

    if regime == "BEARISH":
        if rs["relative_strength_status"] == "OUTPERFORMING_IHSG" and rr2 >= MIN_RR_TARGET_2:
            trade_action = "ACCUMULATION_WATCH"
            reason_bits.append("bearish_ihsg_downgrades_buy_setup_despite_relative_strength")
        else:
            return _no_trade_plan(
                "ACCUMULATION_WATCH",
                "IHSG bearish; buy agresif tidak diizinkan tanpa relative strength kuat dan RR memadai.",
                confidence,
                macro_permission,
            )
    elif regime == "SIDEWAYS":
        trade_action = "ACCUMULATION_WATCH"
        confidence = max(0, confidence - 10)
        reason_bits.append("sideways_ihsg_reduces_confidence")

    return {
        "trade_action": trade_action,
        "entry_type": entry_type,
        "entry_point": _round_price(entry),
        "target_point_1": _round_price(target1),
        "target_point_2": _round_price(target2),
        "cut_loss_point": _round_price(cut_loss),
        "risk_per_share": _round_price(risk),
        "reward_to_target_1": _round_price(reward1),
        "reward_to_target_2": _round_price(reward2),
        "rr_target_1": round(rr1, 2),
        "rr_target_2": round(rr2, 2),
        "position_invalidated_if": f"Harga close harian di bawah {_round_price(cut_loss)}.",
        "trade_reason": ", ".join(reason_bits),
        "macro_confirmation": macro_permission,
        "confidence": confidence,
    }
