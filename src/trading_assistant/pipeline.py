from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Sequence

from trading_assistant.data_loader import fetch_ohlcv, save_raw_data
from trading_assistant.data_quality import evaluate_quality
from trading_assistant.engines import enrich_market_frame
from trading_assistant.indicators.atr import add_atr
from trading_assistant.logging_utils import configure_ingestion_logger
from trading_assistant.market_regime import IHSG_TICKER, screen_ihsg_regime
from trading_assistant.market_data.registry import build_default_registry
from trading_assistant.market_breadth import compute_market_breadth
from trading_assistant.ai_context import build_ai_market_context
from trading_assistant.news import DEFAULT_CNBC_RSS_URL, apply_news_confirmation, build_news_context, fetch_market_news, fetch_rss_news
from trading_assistant.reporting import (
    flatten_trade_analysis,
    latest_summary_row,
    quality_report_rows,
    save_processed_data,
    write_json,
    write_summary,
)
from trading_assistant.trade_plan import build_trade_analysis
from trading_assistant.universe import LQ45_TICKERS


def run_phase1(
    tickers: Sequence[str] | None = None,
    period: str = "5y",
    interval: str = "1d",
    min_bars: int = 500,
    data_dir: Path = Path("data"),
    output_dir: Path = Path("outputs"),
    news_rss_url: str = DEFAULT_CNBC_RSS_URL,
    analytics_engine: str = "fincept",
    provider_priority: Sequence[str] | None = None,
    idx_data_dir: Path | None = None,
    eodhd_token: str | None = None,
    cross_validate: bool = True,
) -> dict:
    selected_tickers = list(tickers or LQ45_TICKERS)
    logger = configure_ingestion_logger()
    metadata_records: list[dict] = []
    quality_records: dict[str, dict] = {}
    summary_rows: list[dict] = []
    analysis_records: list[dict] = []
    trade_plan_rows: list[dict] = []
    provider_registry = build_default_registry(data_dir, provider_priority, idx_data_dir, eodhd_token, cross_validate)
    breadth_frames: dict[str, object] = {}
    if news_rss_url == DEFAULT_CNBC_RSS_URL:
        news_items, news_feed_status = fetch_market_news()
    else:
        news_items, news_feed_status = fetch_rss_news(url=news_rss_url, source_name="CUSTOM")

    logger.info("phase1_start tickers=%s period=%s interval=%s", len(selected_tickers), period, interval)
    logger.info("news_fetch status=%s source=%s items=%s", news_feed_status.get("status"), news_feed_status.get("source", "multi-source"), news_feed_status.get("items", 0))
    ihsg_fetch = fetch_ohlcv(
        ticker=IHSG_TICKER,
        period=period,
        interval=interval,
        cache_dir=data_dir / "cache" / "yfinance", provider_registry=provider_registry,
    )
    save_raw_data(ihsg_fetch.data, "IHSG", data_dir)
    ihsg_quality = evaluate_quality(ihsg_fetch.data, min_bars=min_bars)
    ihsg_result, ihsg_processed = screen_ihsg_regime(ihsg_fetch.data, ihsg_quality.status)
    if not ihsg_processed.empty:
        ihsg_processed = add_atr(ihsg_processed)
        save_processed_data(ihsg_processed, "IHSG", data_dir)
    macro_payload = ihsg_result.to_dict()
    logger.info("ihsg status=%s regime=%s rows=%s", ihsg_quality.status, ihsg_result.ihsg_regime, len(ihsg_fetch.data))

    for ticker in selected_tickers:
        logger.info("fetch_start ticker=%s", ticker)
        fetched = fetch_ohlcv(
            ticker=ticker,
            period=period,
            interval=interval,
            cache_dir=data_dir / "cache" / "yfinance", provider_registry=provider_registry,
        )
        raw_df = fetched.data
        metadata = dict(fetched.metadata)

        if metadata["status"] == "FETCH_ERROR":
            engine_result = enrich_market_frame(raw_df, analytics_engine)
            metadata.update(engine_result.metadata())
            quality_payload = {
                "status": "FETCH_ERROR",
                "flags": ["fetch_error"],
                "metrics": {"rows": 0},
            }
            metadata["quality_flags"] = quality_payload["flags"]
            metadata_records.append(metadata)
            quality_records[ticker] = quality_payload
            summary_rows.append(latest_summary_row(ticker, raw_df, quality_payload, metadata, macro_payload))
            analysis = build_trade_analysis(ticker, raw_df, "FETCH_ERROR", macro_payload, ihsg_processed)
            analysis_payload = apply_news_confirmation(
                analysis.to_dict(),
                build_news_context(ticker, news_items) if news_feed_status.get("status") == "OK" else {
                    "news_status": news_feed_status.get("status"),
                    "news_sentiment": "NEUTRAL",
                    "news_score": 0,
                    "matched_articles": [],
                },
            )
            analysis_records.append(analysis_payload)
            trade_plan_rows.append(flatten_trade_analysis(analysis_payload))
            logger.info("fetch_error ticker=%s error=%s", ticker, metadata.get("error"))
            continue

        save_raw_data(raw_df, ticker, data_dir)
        quality = evaluate_quality(raw_df, min_bars=min_bars)
        quality_payload = {
            "status": quality.status,
            "flags": quality.flags,
            "metrics": quality.metrics,
        }
        metadata["status"] = quality.status
        metadata["quality_flags"] = quality.flags

        engine_result = enrich_market_frame(raw_df, analytics_engine)
        metadata.update(engine_result.metadata())
        processed_df = engine_result.frame
        breadth_frames[ticker] = raw_df
        if not processed_df.empty:
            save_processed_data(processed_df, ticker, data_dir)
        if engine_result.status == "FALLBACK_NATIVE":
            logger.warning(
                "analytics_engine_fallback ticker=%s requested=%s error=%s",
                ticker,
                analytics_engine,
                engine_result.error,
            )

        metadata_records.append(metadata)
        quality_records[ticker] = quality_payload
        analysis = build_trade_analysis(ticker, processed_df, quality.status, macro_payload, ihsg_processed)
        news_context = build_news_context(ticker, news_items) if news_feed_status.get("status") == "OK" else {
            "news_status": news_feed_status.get("status"),
            "news_sentiment": "NEUTRAL",
            "news_score": 0,
            "matched_articles": [],
        }
        analysis_payload = apply_news_confirmation(analysis.to_dict(), news_context)
        analysis_payload["ai_context"] = build_ai_market_context(
            ticker, processed_df, quality_payload, metadata, macro_payload, analysis_payload)
        analysis_records.append(analysis_payload)
        trade_plan_rows.append(flatten_trade_analysis(analysis_payload))
        summary = latest_summary_row(ticker, processed_df, quality_payload, metadata, macro_payload)
        summary.update(flatten_trade_analysis(analysis_payload))
        summary_rows.append(summary)
        logger.info("fetch_done ticker=%s status=%s rows=%s", ticker, quality.status, len(raw_df))

    metadata_path = output_dir / "metadata.json"
    quality_path = output_dir / "data_quality.json"
    quality_report_path = output_dir / "data_quality_report.csv"
    ihsg_path = output_dir / "ihsg_regime.json"
    news_path = output_dir / "market_news.json"
    analysis_path = output_dir / "analysis.json"
    trade_plan_path = output_dir / "trade_plans.csv"
    summary_path = output_dir / "watchlist.csv"
    breadth_path = output_dir / "market_breadth.csv"
    breadth_json_path = output_dir / "market_breadth.json"
    breadth_df, breadth_latest = compute_market_breadth(
        breadth_frames, expected_universe_size=len(selected_tickers), universe_name="LQ45",
        universe_source="STATIC_CONFIG_LQ45_TICKERS")
    write_json(metadata_path, metadata_records)
    write_json(quality_path, quality_records)
    write_summary(quality_report_path, quality_report_rows(metadata_records, quality_records))
    write_json(ihsg_path, macro_payload)
    write_json(news_path, {"feed": news_feed_status, "items": [item.__dict__ for item in news_items]})
    write_json(analysis_path, analysis_records)
    write_summary(trade_plan_path, trade_plan_rows)
    write_summary(summary_path, summary_rows)
    write_summary(breadth_path, breadth_df.to_dict("records"))
    write_json(breadth_json_path, breadth_latest)
    logger.info("phase1_complete output_dir=%s", output_dir)

    status_counts = Counter(record["status"] for record in metadata_records)
    engine_status_counts = Counter(
        record.get("analytics_engine_status", "UNKNOWN")
        for record in metadata_records
    )
    return {
        "processed": len(selected_tickers),
        "status_counts": dict(status_counts),
        "analytics_engine_requested": analytics_engine,
        "analytics_engine_status_counts": dict(engine_status_counts),
        "metadata_path": str(metadata_path),
        "quality_path": str(quality_path),
        "quality_report_path": str(quality_report_path),
        "ihsg_path": str(ihsg_path),
        "news_path": str(news_path),
        "analysis_path": str(analysis_path),
        "trade_plan_path": str(trade_plan_path),
        "summary_path": str(summary_path),
        "breadth_path": str(breadth_path),
        "breadth_json_path": str(breadth_json_path),
        "breadth_status": breadth_latest.get("status"),
        "ihsg_regime": macro_payload["ihsg_regime"],
        "macro_permission": macro_payload["macro_permission"],
    }
