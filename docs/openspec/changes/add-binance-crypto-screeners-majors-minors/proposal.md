## Proposal: Binance crypto screeners (majors/minors style)

### Goal
Create simple, reproducible Binance spot/perp "screeners" analogous to forex `majors`/`minors`, built on top of the existing tradeable base universes.

### Why
- Provide stable, ergonomic universe selectors for strategy research
- Keep base universes tradeable-first (liquidity + exclusions + dedup)
- Push strategy-specific ranking/filters (incl. volatility) to analytics (DuckDB)

### Proposed tiers (implemented)
- **Base**: `binance_{spot,perp}_base` (alias) -> `binance_{spot,perp}_tradeable_base`
- **Largecap**: `binance_{spot,perp}_largecap` (alias) -> `binance_{spot,perp}_tradeable_mcap_cs`
- **Snapshot**: `binance_{spot,perp}_snapshot` (alias) -> `binance_{spot,perp}_top100`

### Future (explicit majors/minors)
Implement explicit majors/minors universes using the CoinScreener market-cap rank list:
- `binance_{spot,perp}_majors`: ranks 1..20 intersect tradeable gates
- `binance_{spot,perp}_minors`: ranks 21..200 intersect tradeable gates

### Strategy mapping
- TS strategies default to `*_base`
- CS strategies default to `*_largecap`

### Scanner mapping (recommended)
- Opportunity scanner: default to `majors` (and optionally `minors` for breadth)
