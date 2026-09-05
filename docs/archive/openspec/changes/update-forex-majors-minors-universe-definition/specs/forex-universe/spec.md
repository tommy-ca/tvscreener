# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: Forex majors/minors universes are deterministic
The system SHALL provide deterministic forex majors/minors universes resolved without network calls.

#### Scenario: Majors resolve to a fixed USD-pair list
- **GIVEN** `asset_type=forex`
- **WHEN** the operator selects `--universe majors`
- **THEN** the resolved pair set equals:
  - `EURUSD`, `GBPUSD`, `USDJPY`, `USDCHF`, `USDCAD`, `AUDUSD`, `NZDUSD`

#### Scenario: Minors exclude USD
- **GIVEN** `asset_type=forex`
- **WHEN** the operator selects `--universe minors`
- **THEN** no resolved pair contains the substring `USD`

#### Scenario: Minors cover the full cross set (unique)
- **GIVEN** the majors currency set is `{EUR, GBP, JPY, CHF, CAD, AUD, NZD}` (excluding `USD`)
- **WHEN** the operator selects `--universe minors`
- **THEN** the resolved universe contains exactly 21 unique crosses (one orientation per cross)

### Requirement: Forex pre-analytics filtering produces one row per PAIR
The system SHOULD deduplicate forex scan results to one best row per `PAIR` before analytics ranking.

#### Scenario: Exchange expansion and dedup selects one row per pair
- **GIVEN** a forex scan requests pairs across multiple exchanges
- **WHEN** results are normalized and deduplicated
- **THEN** the output contains at most one row per `PAIR` using exchange priority and liquidity heuristics
