# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Lakehouse namespace layout (scalable, multi-asset, multi-dataset)

### Design principles
- **Explicit isolation**: avoid nullable, asset-specific columns by isolating schemas by dataset and by instrument type.
- **Stable dataset names**: table names are dataset taxonomy values (`screener_snapshot`, `market_klines`, `deriv_funding`).
- **Dimension-first namespace**: put asset/instrument/stage in the namespace to keep table names stable.
- **Incremental adoption**: preserve existing `tvscreener.*` tables via aliases/compatibility during migration.

### Dimensions

Required namespace dimensions:
- `asset_type`: `forex | crypto | stock | futures | bond | ...`
- `instrument_type`:
  - forex: `spot | cfd | spreadbet | all` (existing concept)
  - crypto: `spot | perp` (TradingView often reports perps as `Type=swap`)
  - futures: `future` (or venue-specific contract class)
- `stage`: `bronze | silver | gold | product`

`dataset` is the table name.

### Canonical identifier (logical)

`tvscreener.<asset_type>.<instrument_type>.<stage>.<dataset>`

Examples:
- `tvscreener.forex.cfd.bronze.screener_snapshot`
- `tvscreener.crypto.spot.gold.screener_snapshot`
- `tvscreener.crypto.perp.product.signals_latest`

### Physical encoding (compatibility)

If the catalog/backend/tooling does not support multi-level namespaces cleanly, encode the namespace as a single segment:

`tvscreener_<asset_type>_<instrument_type>_<stage>.<dataset>`

Examples:
- `tvscreener_crypto_spot_gold.screener_snapshot`
- `tvscreener_crypto_perp_product.signals_latest`

### Implementation note (current repo)
The current `LakehouseManager` accepts Iceberg identifiers of the form `namespace.table` (single-level namespace).
So `tvscreener_crypto_spot_gold.screener_snapshot` is the current **physical** encoding used for the scalable layout.
The nested form remains the logical model for docs and long-term catalog compatibility.

### Why include `instrument_type`
Crypto spot and perps can share many market fields but differ in derivative-only concepts (funding, open interest)
and in subtle semantics (mark price vs last price, contract multipliers, etc.). Including `instrument_type` prevents:

- schema churn / many nullable columns
- accidental joins across incompatible instruments
- overwrite scope bugs where spot writes replace perps

### Relationship to dataset taxonomy
This layout is orthogonal to dataset taxonomy:
- taxonomy decides **what tables exist** (`screener_snapshot`, `market_klines`, `deriv_funding`)
- namespace layout decides **where those tables live** (isolation by asset/instrument/stage)

### Migration plan (high level)
- Keep current tables (`tvscreener.bronze`, `tvscreener.silver`, `tvscreener.gold`, `tvscreener.signals_latest`) as
  compatibility aliases for the forex default instrument_type.
- Introduce new table ids for crypto spot/perps using the new namespace layout.
- Add a lakehouse manager resolver that maps logical ids to physical ids (nested or flattened).
