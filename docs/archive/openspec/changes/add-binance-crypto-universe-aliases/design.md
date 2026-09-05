# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Universe aliases

### Why
Forex has simple universe selectors (`majors`, `minors`).
For Binance crypto, the recommended strategy bases are tradeable-first universes.
Aliases make CLI/config usage shorter while preserving the canonical universe names.

### Where aliases apply
- CLI `--universe` accepts aliases.
- Orchestrator normalizes aliases before routing to universe builders.
- Audit/report artifacts still use canonical universe folder names.
