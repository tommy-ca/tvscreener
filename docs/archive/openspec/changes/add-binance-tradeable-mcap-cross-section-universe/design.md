# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Tradeable market-cap cross-section universes

### Why
`*_mcap_top100` is good for coverage audits but suffers mapping loss.
`*_tradeable_base` is excellent for tradeability but not market-cap anchored.

The cross-section universe combines both:
- market-cap anchored membership
- tradeable and liquid candidates

### Intended usage
- Use `*_tradeable_mcap_cs` as the default universe for CSMOM/CSMR.
- Use `*_tradeable_base` for TS strategies that want broader membership.
