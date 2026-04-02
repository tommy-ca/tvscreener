# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: Strategy families can run atop Binance universes
The system SHALL support running strategy analytics atop Binance crypto universes.

#### Scenario: Strategies share the same base universe
- **GIVEN** `binance_{spot,perp}_tradeable_base`
- **WHEN** any of TSMOM/TSMR/CSMOM/CSMR pipelines run
- **THEN** they MAY use the same base universe input and differ only by analytics-stage filters/rankers

#### Scenario: Base universe readiness is auditable
- **GIVEN** a base universe intended for strategy inputs
- **WHEN** `tvscreener-scan review binance-universes --strict` is executed
- **THEN** it produces sufficient artifacts to validate quote purity, dedup, liquidity distribution, and risky exclusions

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
