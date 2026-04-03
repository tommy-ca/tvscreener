# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Tasks: Binance tradeable base universes

- [x] Implement `binance_{spot,perp}_tradeable_base` universe selectors
- [x] Add CLI wiring and include in `audit binance-universes`
- [x] Add unit tests asserting quote-asset allowlist and one-per-base behavior
- [x] Add Prefect batch templates for both universes
