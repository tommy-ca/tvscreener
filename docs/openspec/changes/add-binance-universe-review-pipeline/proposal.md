## Proposal: One-shot Binance universe review pipeline

### Goal
Make it easy to review and audit Binance spot/perp universes using the DuckDB analytics pipeline, with a single command.

### Scope
- Add a CLI command that runs:
  1) `audit binance-universes` (writes `artifacts/audits/...`)
  2) `report binance-universes` (writes `artifacts/reports/...`)
- Optional strict mode to fail when audit errors exist.
