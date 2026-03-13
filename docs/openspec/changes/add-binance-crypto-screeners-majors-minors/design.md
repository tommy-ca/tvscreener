## Design: Binance crypto screeners

### Principle
Base universes focus on tradability:
- quote normalization (USDT/USDC)
- liquidity floors
- stable/wrapped exclusions
- dedup to one ticker per base

Volatility is persisted for later analytics-stage ranking/filtering.

### Screener-style selectors
Provide stable, ergonomic universe names:

- `binance_{spot,perp}_base` -> tradeable base
- `binance_{spot,perp}_largecap` -> market-cap anchored tradeable cross-section
- `binance_{spot,perp}_snapshot` -> top-by-volume snapshot

For parity with forex CLI usage, `--universe majors|minors` maps to the crypto majors/minors
when `asset_type=crypto` and `instrument_type` is set.

### Majors/minors

- `binance_{spot,perp}_majors`: market-cap ranks 1..20 intersect tradeable gates
- `binance_{spot,perp}_minors`: market-cap ranks 21..200 intersect tradeable gates

### Audit readiness
All screeners are reviewed via:

```bash
uv run tvscreener-scan review binance-universes --strict
```

Use `## Strategy Readiness` as the primary go/no-go table.

For opportunity scanning, start with `majors` by default (forex-like), then expand to `minors` when you want more breadth.
