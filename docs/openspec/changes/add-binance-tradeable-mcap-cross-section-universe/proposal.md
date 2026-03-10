## Proposal: Binance tradeable market-cap cross-section universes

### Goal
Create cross-sectional universes anchored to market cap while preserving tradeability:

- `binance_spot_tradeable_mcap_cs`
- `binance_perp_tradeable_mcap_cs`

These are intended as default universes for **cross-sectional** strategies (CSMOM, CSMR).

### Selection rules
- Seed base assets from TradingView top 100 coins by market cap
- Intersect with the Binance tradeable base gates:
  - quote assets allowlist
  - stable/wrapped exclusions
  - liquidity floor
  - one ticker per base (prefer USDT)

### Output
Persist `universe.json` with `market_cap_bases`, `included_bases`, `missing_bases`, and per-ticker metrics.
