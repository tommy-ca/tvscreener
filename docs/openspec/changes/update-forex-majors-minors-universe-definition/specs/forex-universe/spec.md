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

### Requirement: Forex pre-analytics filtering produces one row per PAIR
The system SHOULD deduplicate forex scan results to one best row per `PAIR` before analytics ranking.

#### Scenario: Exchange expansion and dedup selects one row per pair
- **GIVEN** a forex scan requests pairs across multiple exchanges
- **WHEN** results are normalized and deduplicated
- **THEN** the output contains at most one row per `PAIR` using exchange priority and liquidity heuristics
