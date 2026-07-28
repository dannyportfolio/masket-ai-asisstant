from __future__ import annotations

import pandas as pd


def compute_market_breadth(frames: dict[str, pd.DataFrame], expected_universe_size: int,
                           universe_name: str = "LQ45", universe_source: str = "STATIC_CONFIG") -> tuple[pd.DataFrame, dict]:
    rows = []
    for ticker, frame in frames.items():
        if frame.empty or "close" not in frame.columns:
            continue
        values = frame[["date", "close", "volume"]].copy()
        values["ticker"] = ticker
        values["return_1d"] = pd.to_numeric(values["close"], errors="coerce").pct_change()
        rows.append(values)
    if not rows:
        empty = pd.DataFrame()
        return empty, {"status": "DATA_MISSING", "universe": universe_name, "breadth_scope": "SELECTED_UNIVERSE_ONLY"}
    all_rows = pd.concat(rows, ignore_index=True)
    records = []
    ad_line = 0
    for date, group in all_rows.groupby("date", sort=True):
        adv = int((group["return_1d"] > 0).sum())
        dec = int((group["return_1d"] < 0).sum())
        unchanged = int((group["return_1d"] == 0).sum())
        ad_line += adv - dec
        records.append({"date": date, "universe": universe_name, "universe_source": universe_source,
                        "expected_universe_size": expected_universe_size, "observed_tickers": int(group["ticker"].nunique()),
                        "coverage_pct": round(group["ticker"].nunique() / max(expected_universe_size, 1) * 100, 2),
                        "advancers": adv, "decliners": dec, "unchanged": unchanged, "net_advances": adv - dec,
                        "advance_decline_ratio": round(adv / dec, 4) if dec else None, "advance_decline_line": ad_line,
                        "total_volume": float(group["volume"].sum()),
                        "advancing_volume": float(group.loc[group["return_1d"] > 0, "volume"].sum()),
                        "declining_volume": float(group.loc[group["return_1d"] < 0, "volume"].sum()),
                        "status": "OK" if group["ticker"].nunique() >= expected_universe_size else "PARTIAL_COVERAGE",
                        "breadth_scope": "SELECTED_UNIVERSE_ONLY", "is_full_market_breadth": False})
    result = pd.DataFrame(records)
    return result, result.iloc[-1].to_dict()
