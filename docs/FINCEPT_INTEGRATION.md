# Fincept Engine Integration

## Current Status

FinceptTerminal is pinned as a Git submodule at `vendor/FinceptTerminal` on
commit `fec23dc78c935e001394ea8df3f820eddd0823a0` (2026-07-14).

D-Markets uses only Fincept's Python technical-analysis engine. The local sparse
checkout contains the technical modules, dependency manifests, and license
documents; Qt, CMake, MSVC, screen code, and the former GUI bridge are not part
of the runtime path.

## Runtime Flow

```text
Yahoo Finance fetch
  -> D-Markets data-quality gate
  -> Fincept technical engine
  -> D-Markets compatibility and IDX-specific indicators
  -> IHSG gate, news confirmation, trade plan, CSV/JSON reports
```

The adapter lives in `src/trading_assistant/engines`. Fincept is the default
analytics engine:

```powershell
.\.venv\Scripts\python.exe run_trading_assistant.py --analytics-engine fincept
```

The adapter imports the pinned `compute_technicals.py` module in-process. It
does not launch a GUI, start one subprocess per ticker, or ask Fincept to
download the same market data again.

## Compatibility Contract

Fincept supplies its technical set, including RSI, MACD, ADX, OBV,
Bollinger Bands, ATR, CMF, and cumulative return. D-Markets disables moving
average outputs at the adapter boundary, so `ma_*`, `sma_*`, `ema_*`, and
`wma_*` fields are not part of the active report contract.

| D-Markets field | Source |
|---|---|
| `cmf_20` | Fincept `cmf` |
| `atr_14` | Fincept `atr` |
| `cmf_10`, `cmf_60` | D-Markets IDX analysis windows |
| VPA and effort-vs-result fields | D-Markets IDX-specific layer |

IHSG regime rules, data-quality statuses, news confirmation, and trade-plan
contracts remain owned by D-Markets.

## Failure Behavior

If the submodule or `ta==0.11.0` dependency is unavailable, a ticker falls back
to the native technical engine instead of aborting the market run. The same
fallback applies when a ticker has fewer than 60 bars, because Fincept's full
indicator set includes long lookback windows.

The fallback is never silent. Inspect these fields in `outputs/metadata.json`
and `outputs/watchlist.csv`:

- `analytics_engine_requested`
- `analytics_engine_used`
- `analytics_engine_status`
- `analytics_engine_revision`
- `analytics_engine_error`

Valid statuses are `OK`, `FALLBACK_NATIVE`, and `NOT_RUN`.

To force the original implementation for comparison:

```powershell
.\.venv\Scripts\python.exe run_trading_assistant.py --analytics-engine native
```

## Setup

```powershell
git submodule update --init --filter=blob:none vendor/FinceptTerminal
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The Fincept desktop application's large dependency set is intentionally not
installed. D-Markets only adds the upstream technical-engine dependency
`ta==0.11.0`.

## Scope

The Fincept strategy registry/backtest provider is not wired into Phase 1. Its
current runner fetches historical prices again, which would duplicate the
audited D-Markets ingestion flow. `--with-backtest` therefore remains a roadmap
flag until a local-data provider boundary is added.

## License Gate

FinceptTerminal includes AGPL-3.0 code and separate commercial terms. Upstream
states that commercial and internal-company use, including wrappers and
derivative integrations, requires a paid commercial license. Review:

- `vendor/FinceptTerminal/LICENSE`
- `vendor/FinceptTerminal/docs/COMMERCIAL_LICENSE.md`

Treat this integration as evaluation/personal-use code until the intended use
has been reviewed against those terms. This is not legal advice.
