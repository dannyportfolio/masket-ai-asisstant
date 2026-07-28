# Data Source Matrix

| Feature | Primary Source | Secondary | Fallback | Realtime | Cost | Notes |
|---|---|---|---|---|---|---|
| IDX historical OHLCV | Licensed IDX vendor drop | EODHD | Yahoo/cache | No | Paid or plan-dependent | Preserve source metadata |
| IHSG | Licensed index feed | Yahoo `^JKSE` | cache | No in current pipeline | Paid/plan-dependent | EODHD index symbol needs configuration |
| LQ45 / IDX30 / IDX80 | Licensed index/universe feed | configured files | static config | No | Paid/plan-dependent | Current built-in universe is static LQ45 |
| Intraday candles | Licensed IDX/broker API | none | none | Potentially | Paid | Do not label Yahoo history realtime |
| Quotes / trades | Licensed broker/exchange API | none | none | Yes | Paid | Not present in current repo |
| Market breadth | Derived from observed OHLCV | none | none | Batch | Included | `PARTIAL_COVERAGE` when universe is incomplete |
| Fundamentals | Dedicated licensed fundamentals provider | none | none | No | Provider-specific | Not fabricated from OHLCV |
| Corporate actions | IDX/vendor corporate action feed | none | none | No | Provider-specific | Adjustment validation required |
| Foreign flow | Licensed IDX/broker feed | none | none | Feed-dependent | Paid | Disabled when unavailable |
| Broker summary | Licensed broker/market-data feed | none | none | Feed-dependent | Paid | No legal public fallback assumed |
| Orderbook | Licensed broker/exchange feed | none | none | Yes | Paid | Requires websocket or polling contract |
| Macro | Official BI/BPS/market sources | existing feeds | none | Usually delayed | Mixed | Add adapters only for used indicators |
| News | Existing RSS aggregation | provider APIs | none | Delayed | Mixed | Sentiment must retain article provenance |

Open-source connectors such as OpenBB-style abstractions and Fincept-style analytics can improve software integration, but they do not grant free IDX realtime or redistribution rights. Alpaca and US-focused Polygon/Massive/SEC/FRED sources are not selected as core IDX providers; they are only relevant for explicitly requested global comparison or macro signals.
