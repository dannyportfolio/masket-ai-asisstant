from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from trading_assistant.pipeline import run_phase1
from trading_assistant.news import DEFAULT_CNBC_RSS_URL
from trading_assistant.engines import ANALYTICS_ENGINES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run IDX LQ45 Trading Assistant Phase 1.")
    parser.add_argument(
        "--tickers",
        help="Comma-separated Yahoo Finance tickers. Defaults to the static LQ45 universe.",
    )
    parser.add_argument("--period", default="5y", help="Yahoo Finance history period.")
    parser.add_argument("--interval", default="1d", help="Yahoo Finance interval.")
    parser.add_argument("--min-bars", type=int, default=500, help="Minimum bars for OK status.")
    parser.add_argument("--output-dir", default="outputs", help="Run artifact output directory.")
    parser.add_argument("--data-dir", default="data", help="Local data directory.")
    parser.add_argument(
        "--analytics-engine",
        default="fincept",
        choices=ANALYTICS_ENGINES,
        help="Technical analytics engine. Fincept is the default; native is the fallback.",
    )
    parser.add_argument("--news-rss-url", default=DEFAULT_CNBC_RSS_URL, help="Custom RSS URL for news confirmation. Defaults use CNBC, IDX, Bloomberg, and Yahoo Finance.")
    parser.add_argument("--provider-priority", default="idx_licensed,eodhd,yahoo", help="Comma-separated provider priority.")
    parser.add_argument("--idx-data-dir", help="Directory containing licensed IDX vendor CSV files.")
    parser.add_argument("--eodhd-token", help="EODHD API token; may also be provided via EODHD_API_TOKEN.")
    parser.add_argument("--no-cross-validate", action="store_true", help="Disable provider cross-validation hooks.")
    parser.add_argument("--cnbc-rss-url", help="Deprecated alias for --news-rss-url.")
    parser.add_argument(
        "--universe",
        default="LQ45",
        choices=["LQ45"],
        help="Universe to run. Phase 1 supports LQ45.",
    )
    parser.add_argument(
        "--with-backtest",
        action="store_true",
        help="Accepted for roadmap compatibility; backtest starts in a later phase.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tickers = None
    if args.tickers:
        tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]

    result = run_phase1(
        tickers=tickers,
        period=args.period,
        interval=args.interval,
        min_bars=args.min_bars,
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
        news_rss_url=args.cnbc_rss_url or args.news_rss_url,
        analytics_engine=args.analytics_engine,
        provider_priority=tuple(item.strip() for item in args.provider_priority.split(",") if item.strip()),
        idx_data_dir=Path(args.idx_data_dir) if args.idx_data_dir else None,
        eodhd_token=args.eodhd_token,
        cross_validate=not args.no_cross_validate,
    )

    print("Phase 1 complete")
    print(f"Tickers processed : {result['processed']}")
    print(f"OK                : {result['status_counts'].get('OK', 0)}")
    print(f"Data anomaly      : {result['status_counts'].get('DATA_ANOMALY', 0)}")
    print(f"Stale data        : {result['status_counts'].get('STALE_DATA', 0)}")
    print(f"Insufficient      : {result['status_counts'].get('DATA_INSUFFICIENT', 0)}")
    print(f"Missing           : {result['status_counts'].get('DATA_MISSING', 0)}")
    print(f"Fetch errors      : {result['status_counts'].get('FETCH_ERROR', 0)}")
    print(f"Analytics engine  : {result['analytics_engine_requested']}")
    print(f"Engine OK         : {result['analytics_engine_status_counts'].get('OK', 0)}")
    print(f"Native fallback   : {result['analytics_engine_status_counts'].get('FALLBACK_NATIVE', 0)}")
    print(f"Engine not run    : {result['analytics_engine_status_counts'].get('NOT_RUN', 0)}")
    print(f"IHSG regime       : {result['ihsg_regime']}")
    print(f"Macro permission  : {result['macro_permission']}")
    print(f"IHSG screener     : {result['ihsg_path']}")
    print(f"Market news       : {result['news_path']}")
    print(f"Analysis JSON     : {result['analysis_path']}")
    print(f"Quality report    : {result['quality_report_path']}")
    print(f"Trade plans       : {result['trade_plan_path']}")
    print(f"Summary           : {result['summary_path']}")
    print(f"Market breadth    : {result['breadth_path']} ({result['breadth_status']})")
    if args.with_backtest:
        print("Backtest          : skipped in Phase 1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
