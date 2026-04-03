# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: Binance crypto screener universes exist
The system SHALL provide simple screener-style universe selectors for Binance crypto, analogous to forex `majors`/`minors`.

The system provides `base`/`largecap`/`snapshot` selectors plus explicit `majors`/`minors` universes.

### Requirement: Majors and minors universes exist
The system SHALL provide explicit majors/minors universes for Binance spot/perps.

#### Scenario: Majors are market-cap top20 intersect tradeable gates
- **GIVEN** `universe=binance_spot_majors` (or perp variant)
- **WHEN** the universe selector runs
- **THEN** it uses the market-cap list ranks 1..20 and intersects with tradeable gates (quote allowlist, liquidity floor, exclusions, dedup)
- **AND** it MAY return fewer than 20 instruments due to missing markets or tradeable gates

#### Scenario: Minors are market-cap ranks 21..200 intersect tradeable gates
- **GIVEN** `universe=binance_spot_minors` (or perp variant)
- **WHEN** the universe selector runs
- **THEN** it uses the market-cap list ranks 21..200 and intersects with tradeable gates
- **AND** it MAY return fewer than 180 instruments due to missing markets or tradeable gates

#### Scenario: Base and largecap universes exist
- **GIVEN** the operator selects `binance_spot_base` or `binance_perp_base`
- **WHEN** symbols are resolved
- **THEN** the system uses the canonical tradeable base universes

- **GIVEN** the operator selects `binance_spot_largecap` or `binance_perp_largecap`
- **WHEN** symbols are resolved
- **THEN** the system uses the canonical tradeable market-cap cross-section universes

#### Scenario: Snapshot universes exist
- **GIVEN** the operator selects `binance_spot_snapshot` or `binance_perp_snapshot`
- **WHEN** symbols are resolved
- **THEN** the system uses the canonical top-by-volume snapshot universes

#### Scenario: Majors/minors behave like forex keywords
- **GIVEN** `asset_type=crypto` and `instrument_type=spot`
- **WHEN** the operator selects `--universe majors`
- **THEN** the system resolves symbols from `binance_spot_majors`

- **GIVEN** `asset_type=crypto` and `instrument_type=perp`
- **WHEN** the operator selects `--universe minors`
- **THEN** the system resolves symbols from `binance_perp_minors`

### Requirement: Screener universes are auditable
The system SHALL support auditing readiness for strategy development.

#### Scenario: Review pipeline produces readiness table
- **WHEN** `tvscreener-scan review binance-universes --strict` runs
- **THEN** the report includes `Strategy Readiness` for the strategy base universes

### Requirement: Opportunity scanner can use majors/minors
The system SHOULD support running the opportunity scanner over crypto majors/minors.

#### Scenario: Opportunity scan on majors
- **GIVEN** `asset_type=crypto` and `instrument_type=spot`
- **WHEN** the operator runs the opportunity scanner with `--universe majors`
- **THEN** it scans the Binance spot majors universe
