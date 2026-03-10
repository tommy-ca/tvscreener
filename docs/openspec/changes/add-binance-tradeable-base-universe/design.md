## Design: Tradeable base universes

### Why
Market-cap-seeded universes are useful for coverage audits but suffer from mapping loss.
For strategy development, we want a base universe that is:

- Binance-listed
- liquid
- stable in membership
- aligned between spot and perps

### Universe definitions

`binance_spot_tradeable_base`
- TradingView `CryptoScreener` with `Exchange=BINANCE` and `Type=spot`

`binance_perp_tradeable_base`
- TradingView `CryptoScreener` with `Exchange=BINANCE` and `Type=swap`

Both:
- restrict to quote assets in an allowlist (`USDT`, `USDC`)
- exclude stable/wrapped bases
- apply a liquidity gate (`Volume 24h in USD`) with default floors tuned for parity:
  - spot: `>= 2_500_000`
  - perp: `>= 20_000_000`
- pick one ticker per base (prefer `USDT`)
- sort by USD trading value

### Relationship to strategies
These universes intentionally do not encode momentum/mean-reversion logic.
They only ensure tradeable candidates; ranking and signal generation remain analytics concerns.
