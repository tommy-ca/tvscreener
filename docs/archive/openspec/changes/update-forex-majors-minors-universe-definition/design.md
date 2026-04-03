# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Forex universe resolution and pre-analytics filtering

### Universe resolution

Forex universes are resolved in-process and are intentionally deterministic.

- `--asset-type forex --universe majors` returns a fixed list of pairs (`FOREX_MAJORS`).
- `--asset-type forex --universe minors` returns a fixed list of crosses that exclude `USD` (`FOREX_MINORS`).
- `FOREX_MINORS` targets full cross coverage among the 7 non-USD majors currencies (21 unique crosses).

### Validation (Prefect runner)

```bash
export PREFECT_HOME="$PWD/.prefect-home"
uv run prefect server start --host 127.0.0.1 --port 4200 --background
export PREFECT_API_URL="http://127.0.0.1:4200/api"

uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe majors --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe minors --timeframes 240,60,15 --pipeline data

uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe majors --timeframes 240,60,15 --pipeline analytics --matrix
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe minors --timeframes 240,60,15 --pipeline analytics --matrix
```

Validated artifacts:
- `artifacts/runs/5411af003b204811aae87b4e901142019fd714d3146a7ae7c06b860b9497f4d8/matrix.txt` (majors)
- `artifacts/runs/31dcff1740e7b70bc2e1c6cc58be5dba08cdeaff8183602987f0a2f7a7bd66c5/matrix.txt` (minors)
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

### Strategy fit and risk notes

The forex opportunity scanner is best aligned with:
- directional swing setups with multi-timeframe alignment
- trend/momentum continuation (especially when 240/60 agree)

Common risk drivers to account for outside the scanner:
- economic event risk (CPI, NFP, FOMC)
- regime shifts (risk-on/off)

Recommended: pair forex opportunity outputs with a small macro risk overlay (e.g. NQ/ES/VIX/DXY) to modulate sizing and bias.
