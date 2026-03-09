## ADDED Requirements

### Requirement: CS momentum candidate universes exist
The system SHALL provide Binance crypto candidate universes for cross-sectional momentum trading.

#### Scenario: Spot candidate universe exists
- **GIVEN** `asset_type=crypto`
- **WHEN** `universe=binance_spot_cs_momentum`
- **THEN** the orchestrator returns a list of Binance spot tickers

#### Scenario: Perp candidate universe exists
- **GIVEN** `asset_type=crypto`
- **WHEN** `universe=binance_perp_cs_momentum`
- **THEN** the orchestrator returns a list of Binance perp tickers

### Requirement: Candidate universes are eligibility-filtered, not momentum-filtered
The system SHALL only apply eligibility filters during universe selection.

#### Scenario: Stablecoins are excluded
- **GIVEN** the seed list contains stablecoin bases
- **WHEN** the CS momentum universe is built
- **THEN** stablecoin bases are not present in the final tickers

#### Scenario: Universe is ordered by USD trading value
- **GIVEN** the CS momentum universe is built
- **WHEN** `universe.json` is written
- **THEN** tickers are ordered by `quote_volume_usd` descending

#### Scenario: Spot liquidity floor is lower than perps
- **GIVEN** spot and perp CS momentum universes use default settings
- **WHEN** candidates are selected
- **THEN** the spot universe MAY use a lower `min_quote_volume_usd` than perps
- **AND** the goal is to keep spot/perp candidate set sizes comparable

### Requirement: Universe snapshot artifact is written
The system SHALL persist `universe.json` for CS momentum universes.

#### Scenario: universe.json contains eligibility metadata
- **WHEN** a CS momentum universe is built
- **THEN** `universe.json` includes `requested_tickers`, `missing_tickers`, and per-ticker metrics

#### Scenario: universe.json reports base coverage
- **WHEN** a CS momentum universe is built
- **THEN** `universe.json` includes `included_bases` and `missing_bases`

#### Scenario: Universe mapping supports a quote-asset fallback
- **GIVEN** a base asset does not have a `USDT` market but does have a `USDC` market
- **WHEN** the universe is built with default `quote_assets`
- **THEN** the system MAY include the `USDC` market as a fallback
