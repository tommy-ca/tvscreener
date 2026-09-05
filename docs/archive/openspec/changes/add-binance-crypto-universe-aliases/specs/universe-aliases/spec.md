# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: CLI supports Binance universe aliases
The system SHALL support alias names for Binance crypto universes.

#### Scenario: Alias maps to canonical universe
- **GIVEN** the operator passes `--universe binance_spot_base`
- **WHEN** symbols are resolved
- **THEN** the system uses the same universe builder and constraints as `binance_spot_tradeable_base`

#### Scenario: Aliases exist for base, largecap, and snapshot
- **WHEN** the operator selects a Binance crypto universe
- **THEN** the CLI supports aliases for:
  - base (tradeable base)
  - largecap (tradeable market-cap cross-section)
  - snapshot (top100 by volume)
