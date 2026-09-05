# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## MODIFIED Requirements

### Requirement: Tradeable base universes exclude risky new listings
The system SHALL exclude risky new listings from `binance_{spot,perp}_tradeable_base`.

#### Scenario: Exclude non-mcap bases with short history
- **GIVEN** `universe=binance_spot_tradeable_base` (or perp variant)
- **AND** a candidate base is NOT in the market-cap top100 reference list
- **AND** the candidate has `history_days < min_history_days_non_mcap`
- **WHEN** the universe selector runs
- **THEN** the candidate SHALL be excluded from the returned universe

#### Scenario: Universe snapshot records history length
- **WHEN** the tradeable base universe writes `universe.json`
- **THEN** each row includes `history_days` when TradingView provides bar timestamps

#### Scenario: Universe snapshot records excluded risky candidates
- **WHEN** risky candidates are excluded
- **THEN** `universe.json` includes an `excluded_risky` list with the excluded tickers and their `history_days`
