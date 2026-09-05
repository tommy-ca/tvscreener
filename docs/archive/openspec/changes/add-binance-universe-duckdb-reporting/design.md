# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Universe reporting via DuckDB

### Why
The audit command provides correctness checks, but strategy research needs richer summaries:
- liquidity distributions
- volatility distributions
- quote-asset composition
- overlap between universes

DuckDB is already used in the repo for analytics; reports use DuckDB over in-memory DataFrames derived from `universe.json`.

### Metrics
Per universe:
- ticker count and distinct base count
- min/median/p95 `quote_volume_usd`
- min/median/p95 `volatility_24h_pct`
- quote volume percentiles (p10/p25/p50/p75/p90/p95/p99)
- binned volume distribution counts (USD ranges)
- top volume assets table (per-universe)
- full ticker-level and base-level volume tables written as parquet artifacts
- risky-assets view: non-mcap-top100 bases inside tradeable universes with `history_days` available
- quote-asset distribution

Top100 analysis:
- diagnostics table for `binance_{spot,perp}_top100` (candidate counts through quote/volume/exclusion/dedup steps)

Strategy readiness:
- readiness table for strategy base universes with a conservative default-ready boolean and supporting metrics

Majors/minors:
- majors/minors universes are treated as additional strategy-ready inputs and should appear in the readiness table

Readiness defaults:
- `tradeable_base` and `tradeable_mcap_cs` expect at least 20 members
- `majors` (mcap tier) expects at least 10 members

Scanner readiness:
- report includes a heuristic table for opportunity vs strategy readiness (liquidity distribution + quote purity + dedup)

Recommended defaults (scanner usage):
- Use `majors` for day-to-day opportunity scans (stable, high-liquidity)
- Use `minors` for broader opportunity scans (more breadth, more churn)

Spot top100 (special focus):
- per-quote overview for `binance_spot_top100` (counts, duplicate bases, liquidity/volatility distributions, sample tickers)

Spot universes (breakdown):
- per-quote breakdown per spot universe (counts + volume distributions)

Across universes:
- overlap matrix by ticker
- overlap matrix by base

Spot vs perp audit view:
- per-family parity table comparing spot vs perp universes (counts, base overlap, and median liquidity/volatility)

### Usage

Generate report artifacts from an audit folder:

```bash
uv run tvscreener-scan report binance-universes \
  --in-dir artifacts/audits/binance-universes \
  --out-dir artifacts/reports/binance-universes
```

Run the end-to-end audit+report pipeline:

```bash
uv run tvscreener-scan review binance-universes \
  --audit-out-dir artifacts/audits/binance-universes \
  --report-out-dir artifacts/reports/binance-universes
```

Use `--strict` to fail the command when audit errors exist.

Use `--include-all` to include extended diagnostic universes (market-cap top100 and cs_momentum).

### Interpretation

- Prefer `binance_{spot,perp}_tradeable_base` as the shared strategy base; apply strategy-specific rankers/filters in analytics.
- Use `Spot Quote Breakdown` to confirm spot universes remain USD-quote aligned (USDT/USDC) and to spot quote concentration.
- Treat `binance_{spot,perp}_top100` as a volatility/liquidity snapshot; use `Top100 Diagnostics` to explain any underfill.

For strategy readiness, focus on `binance_{spot,perp}_tradeable_base` and `binance_{spot,perp}_tradeable_mcap_cs`.
