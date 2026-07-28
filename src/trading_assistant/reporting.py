from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pandas as pd


def save_processed_data(df: pd.DataFrame, ticker: str, data_dir: Path) -> Path | None:
    if df.empty:
        return None
    processed_dir = data_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    path = processed_dir / f"{ticker}.csv"
    df.to_csv(path, index=False)
    return path


def latest_summary_row(
    ticker: str,
    df: pd.DataFrame,
    quality: dict,
    metadata: dict,
    macro: dict | None = None,
) -> dict:
    base = {
        "ticker": ticker,
        "status": quality["status"],
        "rows": metadata["rows"],
        "start_date": metadata["start_date"],
        "end_date": metadata["end_date"],
        "quality_flags": ";".join(quality["flags"]),
        "analytics_engine": metadata.get("analytics_engine_used"),
        "analytics_engine_status": metadata.get("analytics_engine_status"),
        "analytics_engine_revision": metadata.get("analytics_engine_revision"),
        "provider": metadata.get("provider"),
        "source": metadata.get("source"),
        "is_delayed": metadata.get("is_delayed"),
        "delay_seconds": metadata.get("delay_seconds"),
    }
    if macro is not None:
        for field in [
            "ihsg_regime",
            "ihsg_trend_score",
            "ihsg_cmf_20",
            "ihsg_cmf_60",
            "ihsg_vpa_signal",
            "macro_permission",
            "macro_reason",
        ]:
            base[field] = macro.get(field)
    if df.empty:
        return base

    latest = df.iloc[-1].to_dict()
    for field in [
        "date",
        "close",
        "volume",
        "cmf_10",
        "cmf_20",
        "cmf_60",
        "atr_14",
        "spread",
        "close_position",
        "volume_ratio_20",
        "spread_ratio_20",
        "narrow_spread_high_volume",
        "effort_no_result_up",
        "effort_no_result_down",
        "low_effort_large_move",
        "relative_volume_20",
        "volume_zscore_20",
        "volume_spike_20",
        "volume_acceleration_5_20",
        "traded_value",
        "volume_signal",
        "vwpa_traded_value",
        "vwpa_value_ratio_20",
        "vwpa_value_percentile_20",
        "vwpa_pressure_20",
        "vwpa_signal",
    ]:
        base[field] = latest.get(field)
    return base


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_summary(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(rows)).to_csv(path, index=False)


def quality_report_rows(metadata_records: list[dict], quality_records: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for metadata in metadata_records:
        ticker = metadata["ticker"]
        quality = quality_records.get(ticker, {"flags": [], "metrics": {}})
        metrics = quality.get("metrics", {})
        rows.append(
            {
                "ticker": ticker,
                "source": metadata.get("source"),
                "fetch_timestamp": metadata.get("fetch_timestamp_utc"),
                "first_date": metadata.get("start_date"),
                "last_date": metadata.get("end_date"),
                "row_count": metadata.get("rows"),
                "missing_ohlcv_count": sum(
                    int(metrics.get(f"missing_{column}", 0))
                    for column in ["open", "high", "low", "close", "volume"]
                ),
                "zero_volume_count": metrics.get("zero_volume_rows", 0),
                "anomaly_count": int(metrics.get("invalid_candle_rows", 0))
                + int(metrics.get("non_positive_ohlc_rows", 0))
                + int(metrics.get("extreme_range_rows", 0)),
                "data_status": metadata.get("status"),
                "quality_flags": ";".join(quality.get("flags", [])),
            }
        )
    return rows


def flatten_trade_analysis(analysis: dict) -> dict:
    trade_plan = analysis.get("trade_plan", {})
    relative_strength = analysis.get("relative_strength", {})
    saturation = analysis.get("saturation_index", {})
    wyckoff_vpa = analysis.get("wyckoff_vpa", {})
    news = analysis.get("news", {})
    return {
        "ticker": analysis.get("ticker"),
        "analysis_date": analysis.get("analysis_date"),
        "data_status": analysis.get("data_status"),
        "trade_action": trade_plan.get("trade_action"),
        "entry_type": trade_plan.get("entry_type"),
        "entry_point": trade_plan.get("entry_point"),
        "target_point_1": trade_plan.get("target_point_1"),
        "target_point_2": trade_plan.get("target_point_2"),
        "cut_loss_point": trade_plan.get("cut_loss_point"),
        "risk_per_share": trade_plan.get("risk_per_share"),
        "reward_to_target_1": trade_plan.get("reward_to_target_1"),
        "reward_to_target_2": trade_plan.get("reward_to_target_2"),
        "rr_target_1": trade_plan.get("rr_target_1"),
        "rr_target_2": trade_plan.get("rr_target_2"),
        "confidence": trade_plan.get("confidence"),
        "relative_strength_20": relative_strength.get("relative_strength_20"),
        "relative_strength_60": relative_strength.get("relative_strength_60"),
        "relative_strength_status": relative_strength.get("relative_strength_status"),
        "accumulation_saturation_index": saturation.get("accumulation_saturation_index"),
        "distribution_saturation_index": saturation.get("distribution_saturation_index"),
        "wyckoff_phase": wyckoff_vpa.get("phase"),
        "vpa_main_signal": wyckoff_vpa.get("main_signal"),
        "vwpa_signal": wyckoff_vpa.get("vwpa_signal"),
        "vwpa_pressure_20": wyckoff_vpa.get("vwpa_pressure_20"),
        "news_status": news.get("news_status"),
        "news_sentiment": news.get("news_sentiment"),
        "news_score": news.get("news_score"),
        "news_confirmation": trade_plan.get("news_confirmation"),
        "trade_reason": trade_plan.get("trade_reason"),
    }
