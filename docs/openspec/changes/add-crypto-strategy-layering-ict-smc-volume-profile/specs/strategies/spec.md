## ADDED Requirements

### Requirement: Strategy families can run atop Binance universes
The system SHALL support running strategy analytics atop Binance crypto universes.

#### Scenario: TSMOM strategy can be evaluated
- **GIVEN** a Binance universe and a `market_bars` dataset
- **WHEN** the TSMOM analytics pipeline runs
- **THEN** it produces ranked candidates and persists results parquet

#### Scenario: CSMOM strategy can be evaluated
- **GIVEN** a Binance universe and a `market_bars` dataset
- **WHEN** the CSMOM analytics pipeline runs
- **THEN** it produces cross-sectional rankings and persists results parquet

### Requirement: ICT/SMC and volume profile features are derived from bars
The system SHALL compute ICT/SMC and volume profile features from `market_bars`.

#### Scenario: SMC features exist
- **WHEN** the SMC feature pipeline runs
- **THEN** `smc_features` is written for each ticker/timeframe

#### Scenario: Volume profile features exist
- **WHEN** the volume profile pipeline runs
- **THEN** `volume_profile` is written for each ticker/timeframe
