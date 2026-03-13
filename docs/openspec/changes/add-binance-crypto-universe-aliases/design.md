## Design: Universe aliases

### Why
Forex has simple universe selectors (`majors`, `minors`).
For Binance crypto, the recommended strategy bases are tradeable-first universes.
Aliases make CLI/config usage shorter while preserving the canonical universe names.

### Where aliases apply
- CLI `--universe` accepts aliases.
- Orchestrator normalizes aliases before routing to universe builders.
- Audit/report artifacts still use canonical universe folder names.
