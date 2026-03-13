## Proposal: Binance crypto universe aliases (majors/minors style)

### Goal
Provide ergonomic universe names (like forex `majors`/`minors`) that map to the recommended Binance spot/perp base universes.

### Aliases
- `binance_spot_base` -> `binance_spot_tradeable_base`
- `binance_perp_base` -> `binance_perp_tradeable_base`
- `binance_spot_largecap` -> `binance_spot_tradeable_mcap_cs`
- `binance_perp_largecap` -> `binance_perp_tradeable_mcap_cs`
- `binance_spot_snapshot` -> `binance_spot_top100`
- `binance_perp_snapshot` -> `binance_perp_top100`

Majors/minors are exposed as canonical universe names:
- `binance_{spot,perp}_majors`
- `binance_{spot,perp}_minors`

These aliases support "screener-style" usage for crypto (see `add-binance-crypto-screeners-majors-minors`).

### Non-goals
- No change to universe construction logic or constraints.
- No strategy-specific ranking/filtering at selection time.
