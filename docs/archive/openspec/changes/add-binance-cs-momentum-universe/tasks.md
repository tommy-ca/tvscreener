# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Tasks: Binance CS momentum universes

- [x] Implement `binance_spot_cs_momentum` and `binance_perp_cs_momentum` universe selectors
- [x] Persist `universe.json` for these universes
- [x] Add Prefect batch templates for both universes
- [x] Add unit tests for exclusion list + liquidity ordering
- [ ] Document how analytics should apply momentum/ROC ranking downstream
