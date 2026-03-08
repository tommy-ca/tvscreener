## Proposal: Scalable lakehouse namespace layout (asset + instrument + stage + dataset)

### Context
The repo is expanding beyond forex into multi-asset and multi-instrument scanning (crypto spot + perps, futures, etc.).
TradingView `/scan` field availability differs by asset and instrument type, and we want to avoid a single wide table
with lots of nullable, asset-specific columns.

The existing docs propose stage-oriented namespaces (e.g. `tvscreener_bronze.screener_snapshot`) and a dataset taxonomy.
This is a solid baseline, but we need a naming design that scales to:

- more `asset_type` values
- more `instrument_type` values (spot vs perp/swap)
- more `dataset_type` values (snapshots vs market bars vs derivative-only datasets)

### Goal
Define a scalable, Iceberg-native naming layout that:

- keeps dataset tables isolated (avoid schema junk drawers)
- keeps asset/instrument-specific schemas from colliding
- remains usable from Python (pyiceberg) and SQL engines
- can be introduced incrementally (compatibility window)

### Candidate layout (nested namespaces)

Logical identifier model:

`tvscreener.<asset_type>.<instrument_type>.<stage>.<dataset>`

Examples:
- `tvscreener.crypto.spot.bronze.screener_snapshot`
- `tvscreener.crypto.perp.gold.screener_snapshot`
- `tvscreener.crypto.perp.silver.deriv_funding`
- `tvscreener.stock.spot.silver.market_klines`

Notes:
- `instrument_type` is explicit to prevent spot/perps from polluting each other.
- `dataset` remains the dataset taxonomy name (e.g. `screener_snapshot`, `market_klines`).

### Compatibility plan (hybrid physical encoding)
Some catalog/backends/tools (and the current namespace provisioning helper) behave best with single-level namespaces.
During transition, allow a flattened encoding that preserves the same logical dimensions:

- `tvscreener_<asset_type>_<instrument_type>_<stage>.<dataset>`
  - Example: `tvscreener_crypto_spot_bronze.screener_snapshot`

The nested namespace form remains the target logical contract; the flattened form is a physical compatibility encoding.

### Non-goals
- Migrating all existing tables immediately
- Enforcing the schema-pack taxonomy for all market-data datasets in this change
