# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Proposal: Binance crypto CS momentum candidate universes (spot + perps)

### Goal
Add Binance crypto universes tailored for cross-sectional momentum trading:

- `binance_spot_cs_momentum`
- `binance_perp_cs_momentum`

These universes are intended to be **candidate sets** (tradeable + liquid) before momentum/ROC filtering and ranking
in analytics.

### Key idea
Use a deterministic, TradingView-driven seed and then apply *only* eligibility filters:

- Seed: top N coins by market cap (TradingView `CoinScreener` `Market Cap Calc`)
- Map to Binance `USDT` markets (spot or perp)
- Exclude stablecoins and wrapped/synthetic bases
- Liquidity gate: min `Volume 24h in USD`
- Order: `Volume 24h in USD` desc

Then, apply momentum/ROC ranking in DuckDB analytics pipelines.
