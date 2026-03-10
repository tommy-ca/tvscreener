## ADDED Requirements

### Requirement: Tradeable market-cap CS universes exist
The system SHALL provide tradeable, market-cap-anchored cross-sectional universes.

#### Scenario: Spot CS universe exists
- **WHEN** `universe=binance_spot_tradeable_mcap_cs`
- **THEN** the system returns Binance spot tickers that are both tradeable and market-cap anchored

#### Scenario: Perp CS universe exists
- **WHEN** `universe=binance_perp_tradeable_mcap_cs`
- **THEN** the system returns Binance perp tickers that are both tradeable and market-cap anchored

### Requirement: Universe snapshot includes base coverage
The system SHALL write `universe.json` with base coverage fields.
