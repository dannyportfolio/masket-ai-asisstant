from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class QualityResult:
    status: str
    flags: list[str]
    metrics: dict


def evaluate_quality(df: pd.DataFrame, min_bars: int = 500, stale_after_days: int = 14) -> QualityResult:
    if df.empty:
        return QualityResult(
            status="DATA_MISSING",
            flags=["empty_dataset"],
            metrics={"rows": 0},
        )

    flags: list[str] = []
    metrics: dict = {"rows": int(len(df))}

    missing_required = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_required:
        return QualityResult(
            status="DATA_MISSING",
            flags=[f"missing_column:{column}" for column in missing_required],
            metrics=metrics,
        )

    work = df.copy()
    for column in ["open", "high", "low", "close", "volume"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
        missing_count = int(work[column].isna().sum())
        metrics[f"missing_{column}"] = missing_count
        if missing_count:
            flags.append(f"missing_values:{column}:{missing_count}")

    non_positive = (
        (work["open"] <= 0)
        | (work["high"] <= 0)
        | (work["low"] <= 0)
        | (work["close"] <= 0)
    )
    non_positive_count = int(non_positive.fillna(False).sum())
    metrics["non_positive_ohlc_rows"] = non_positive_count
    if non_positive_count:
        flags.append(f"non_positive_ohlc_rows:{non_positive_count}")

    if len(work) < min_bars:
        flags.append(f"insufficient_bars:{len(work)}<{min_bars}")

    zero_volume = int((work["volume"].fillna(0) == 0).sum())
    metrics["zero_volume_rows"] = zero_volume
    if zero_volume:
        flags.append(f"zero_volume_rows:{zero_volume}")

    invalid_candles = (
        (work["high"] < work["low"])
        | (work["open"] > work["high"])
        | (work["open"] < work["low"])
        | (work["close"] > work["high"])
        | (work["close"] < work["low"])
    )
    invalid_count = int(invalid_candles.fillna(False).sum())
    metrics["invalid_candle_rows"] = invalid_count
    if invalid_count:
        flags.append(f"invalid_candle_rows:{invalid_count}")

    ranges = work["high"] - work["low"]
    close = work["close"].replace(0, pd.NA)
    range_pct = ranges / close
    extreme_range = int((range_pct > 0.35).fillna(False).sum())
    metrics["extreme_range_rows"] = extreme_range
    if extreme_range:
        flags.append(f"extreme_range_rows:{extreme_range}")

    dates = pd.to_datetime(work["date"], errors="coerce").dropna().sort_values()
    metrics["valid_date_rows"] = int(len(dates))
    if len(dates) >= 2:
        gaps = dates.diff().dt.days.dropna()
        large_gaps = int((gaps > 7).sum())
        metrics["calendar_gaps_gt_7d"] = large_gaps
        if large_gaps:
            flags.append(f"calendar_gaps_gt_7d:{large_gaps}")
        last_date = dates.iloc[-1].date()
        metrics["last_date"] = str(last_date)
        if last_date < date.today() - timedelta(days=stale_after_days):
            flags.append(f"stale_data:last_date:{last_date}")
    else:
        flags.append("insufficient_valid_dates")

    if any(flag.startswith("insufficient_bars") for flag in flags):
        status = "DATA_INSUFFICIENT"
    elif any(
        flag.startswith(("invalid_candle_rows", "non_positive_ohlc_rows", "extreme_range_rows"))
        for flag in flags
    ):
        status = "DATA_ANOMALY"
    elif any(flag.startswith("stale_data") for flag in flags):
        status = "STALE_DATA"
    else:
        status = "OK"

    return QualityResult(status=status, flags=flags, metrics=metrics)
