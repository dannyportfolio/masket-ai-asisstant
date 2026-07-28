from __future__ import annotations

import pandas as pd


def build_ai_market_context(ticker: str, frame: pd.DataFrame, quality: dict,
                            metadata: dict, macro: dict | None = None,
                            analysis: dict | None = None) -> dict:
    latest = frame.iloc[-1].to_dict() if not frame.empty else {}
    analysis_snapshot = dict(analysis or {})
    analysis_snapshot.pop("ai_context", None)
    return {
        "schema_version": "1.0",
        "ticker": ticker,
        "provenance": {"source": metadata.get("source"), "provider": metadata.get("provider"),
                        "retrieved_at": metadata.get("retrieved_at"), "exchange": "IDX"},
        "data_quality": {"status": quality.get("status"), "flags": quality.get("flags", []),
                          "is_delayed": metadata.get("is_delayed", True), "delay_seconds": metadata.get("delay_seconds")},
        "market_context": {"ihsg_regime": (macro or {}).get("ihsg_regime"),
                            "macro_permission": (macro or {}).get("macro_permission")},
        "metrics": {key: latest.get(key) for key in (
            "date", "close", "volume", "relative_volume_20", "volume_zscore_20",
            "volume_spike_20", "volume_acceleration_5_20", "volume_signal", "cmf_20",
            "atr_14", "vwpa_traded_value", "vwpa_value_ratio_20",
            "vwpa_value_percentile_20", "vwpa_pressure_20", "vwpa_signal") if key in latest},
        "analysis": analysis_snapshot,
        "limitations": ["Foreign flow, broker summary, orderbook, and tick data are omitted unless a licensed source supplies them.",
                         "This context is delayed/historical unless provider metadata explicitly says otherwise."],
    }
