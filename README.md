# IDX LQ45 Trading Assistant

Phase 1 builds an audit-ready data foundation for an IDX LQ45 trading assistant.
It downloads real daily OHLCV data from Yahoo Finance, stores raw and processed
files locally, validates data quality, and computes CMF plus basic VPA metrics.

This project is not an auto-trading bot and does not provide guaranteed profit
claims. Outputs are analytical watchlist inputs only.

## What Phase 1 Does

- Downloads LQ45 daily OHLCV data from Yahoo Finance through `yfinance`.
- Writes raw data to `data/raw/{ticker}.csv`.
- Validates missing values, zero volume, invalid candles, date gaps, and bar count.
- Computes CMF windows 10, 20, and 60.
- Computes ATR14.
- Runs the pinned Fincept Python technical engine for RSI, MACD, ADX, OBV,
  volatility bands, and other indicators.
- Screens IHSG (`^JKSE`) as the Phase 1 market-regime gate.
- Reads CNBC Indonesia, IDX, Bloomberg, and Yahoo Finance market news as an auditable news confirmation layer.
- Computes basic VPA candle metrics and effort-vs-result flags.
- Writes enriched data to `data/processed/{ticker}.csv`.
- Writes run artifacts to:
  - `outputs/ihsg_regime.json`
  - `outputs/watchlist.csv`
  - `outputs/analysis.json`
  - `outputs/data_quality_report.csv`
  - `outputs/market_news.json`
  - `logs/ingestion.log`

If Yahoo Finance does not return usable data for a ticker, the system records
`DATA_MISSING`, `DATA_INSUFFICIENT`, `DATA_ANOMALY`, `STALE_DATA`, or
`FETCH_ERROR`. It never fabricates price or volume data.

## Install

```powershell
python -m venv .venv
git submodule update --init --filter=blob:none vendor/FinceptTerminal
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If `python` is not on PATH, use any available Python 3.10+ interpreter.

## Run

Full LQ45 universe:

```powershell
.\.venv\Scripts\python.exe run_trading_assistant.py
```

Small smoke run:

```powershell
.\.venv\Scripts\python.exe run_trading_assistant.py --tickers BBCA.JK,BMRI.JK,TLKM.JK
```

Useful options:

```powershell
.\.venv\Scripts\python.exe run_trading_assistant.py --period 5y --interval 1d --min-bars 500 --analytics-engine fincept
```

Fincept is the default analytics engine. To compare against the original
implementation, pass `--analytics-engine native`. If Fincept is unavailable,
the run continues with native indicators and records `FALLBACK_NATIVE` in
metadata and the watchlist.

Roadmap-compatible command:

```powershell
.\.venv\Scripts\python.exe run_trading_assistant.py --period 5y --universe LQ45 --with-backtest
```

In Phase 1, `--with-backtest` is accepted but skipped; backtesting begins in a
later phase.

## Data Notes

The LQ45 universe is a maintained static list for Phase 1. Later phases can add
an audited universe refresh workflow.

Yahoo Finance availability can vary by ticker and date. Treat quality statuses
in the output files as part of the analysis, not as noise to ignore.

## Fincept Engine Integration

FinceptTerminal is pinned as a separate Git submodule under
`vendor/FinceptTerminal`. D-Markets imports only its Python technical engine;
the Qt GUI and its build toolchain are not used.

```powershell
git submodule update --init --filter=blob:none vendor/FinceptTerminal
.\.venv\Scripts\python.exe run_trading_assistant.py --tickers MDKA.JK --analytics-engine fincept
```

See `docs/FINCEPT_INTEGRATION.md` for the engine boundary, compatibility
mapping, fallback behavior, pinned revision, and upstream license warning.
