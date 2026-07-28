# IDX Market Data Architecture

## Existing architecture

The project is a batch-oriented Python pipeline: provider fetch -> OHLCV normalization -> local CSV artifacts -> quality checks -> native/Fincept-style technical enrichment -> IHSG regime, news confirmation, and trade plans. There is no frontend, API server, database, websocket, Redis, queue, or broker execution layer in the current repository.

The main architectural weakness was that business logic called `yfinance` directly. That made Yahoo both the implementation and the implicit source of truth, with no provider provenance, stale-cache fallback, or licensing boundary.

## New architecture

`ProviderRegistry` now resolves `IDX Licensed File Drop` -> `EODHD` -> `Yahoo Finance` by default. Every provider returns the same normalized frame and metadata. The registry retries retryable failures, records provider attempts, caches successful responses, and can return a last-known stale cache with `STALE_CACHE_FALLBACK`.

The pipeline remains batch-first and file-based, preserving the existing project shape. It now produces volume intelligence, selected-universe breadth, provider metadata, and a structured AI context after quantitative analytics. The breadth scope is explicitly the configured LQ45 list, not all IDX.

## Provider decisions

| Domain | Primary | Secondary | Fallback | Status |
|---|---|---|---|---|
| Licensed IDX OHLCV | IDX vendor file drop | EODHD | Yahoo | Paid/licensing review |
| Historical daily OHLCV | EODHD when token exists | Yahoo | cache | Available/partially available |
| IHSG and index history | Licensed vendor or Yahoo `^JKSE` | EODHD if symbol is configured | cache | Partially available |
| Intraday / quotes / trades | Licensed IDX or broker feed | none | none | Paid data required |
| Fundamentals / corporate actions | Licensed IDX/vendor or dedicated fundamentals provider | none | none | Provider-specific review |
| Breadth / volume analytics | Derived from observed OHLCV | none | none | Available, selected-universe scope |
| Foreign flow / broker summary / orderbook | Licensed IDX/broker feed | none | none | Unavailable without licensed feed |
| Macro and news | Existing RSS and future official macro adapters | none | none | Partially available |

Yahoo/yfinance remains useful as historical fallback, but yfinance is open-source software rather than free redistribution rights for Yahoo data ([yfinance legal note](https://ranaroussi.github.io/yfinance/index.html)). EODHD documents Indonesia exchange coverage and plan limits ([exchange coverage](https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours/), [historical API](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes/)). IDX market data distribution should use the official vendor/member route rather than scraping protected pages ([IDX Mitra BEI](https://www.idx.co.id/id/produk/layanan-data-bei/mitra-bei/), [IDX statistics](https://www.idx.co.id/id/data-pasar/laporan-statistik/statistik/)).

## Roadmap

P0 is implemented: provider abstraction, normalized provenance, retries, cache fallback, data quality foundation, volume intelligence, and selected-universe breadth. P1 should add a licensed intraday/fundamental adapter and sector mappings. P2 should add broker/orderbook/tick adapters only after a valid commercial feed and storage requirement exist. PostgreSQL, ClickHouse, Redis, and BullMQ should be introduced only when an API, realtime stream, or multi-user workload justifies them.
