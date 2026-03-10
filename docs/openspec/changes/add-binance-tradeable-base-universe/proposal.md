## Proposal: Binance tradeable base universes (spot + perps)

### Goal
Add Binance-first base universes optimized for tradeable strategy candidates:

- `binance_spot_tradeable_base`
- `binance_perp_tradeable_base`

These are intended to be the default substrate for TS/CS momentum and mean-reversion analytics.

### Selection rules
- TradingView crypto `/scan`
- Exchange: `BINANCE`
- Instrument type: `spot` (spot universe) or `swap` (perp universe)
- Quote assets allowlist: `USDT`, fallback `USDC`
- Exclude stablecoin and wrapped/synthetic bases
- Liquidity gate defaults (configurable):
  - spot: `>= 2_500_000`
  - perp: `>= 20_000_000`
- Pick at most one market per base asset (prefer `USDT`)
- Order by `Volume 24h in USD` desc

### Artifacts
Persist `universe.json` with:
- `included_bases`, `missing_bases`
- per-ticker `quote_volume_usd`, `volatility_24h_pct`
