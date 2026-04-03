# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Proposal: One-shot Binance universe review pipeline

### Goal
Make it easy to review and audit Binance spot/perp universes using the DuckDB analytics pipeline, with a single command.

### Scope
- Add a CLI command that runs:
  1) `audit binance-universes` (writes `artifacts/audits/...`)
  2) `report binance-universes` (writes `artifacts/reports/...`)
- Optional strict mode to fail when audit errors exist.
