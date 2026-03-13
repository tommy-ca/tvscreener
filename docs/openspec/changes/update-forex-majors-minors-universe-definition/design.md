## Design: Forex universe resolution and pre-analytics filtering

### Universe resolution

Forex universes are resolved in-process and are intentionally deterministic.

- `--asset-type forex --universe majors` returns a fixed list of pairs (`FOREX_MAJORS`).
- `--asset-type forex --universe minors` returns a fixed list of crosses that exclude `USD` (`FOREX_MINORS`).
- `FOREX_MINORS` targets full cross coverage among the 7 non-USD majors currencies (21 unique crosses).
- `--asset-type forex --universe all` (or unset) returns `DEFAULT_FOREX_PAIRS`.

### Pre-analytics filtering

Forex opportunity/strategy scans operate on *pairs*, but the upstream TradingView scan operates on *tickers*.

Before analytics ranking and matrix rendering:

1) Pair expansion to tickers
- Each requested pair is expanded across `preferred_exchanges` into tickers like `OANDA:EURUSD`.

2) Contract type filter
- Results are filtered by `contract_type` (default `cfd`).

3) Deduplication to one row per `PAIR`
- Duplicate rows for the same `PAIR` (multiple exchanges, multiple symbol variants) are normalized and reduced to a single best row using:
  - canonical-pair preference
  - `EXCHANGE_PRIORITY`
  - 10-day average volume as a tie-breaker

This ensures majors/minors behave as stable, operator-friendly universes before any analytics-stage ranking/filtering.
