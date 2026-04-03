# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: Tradeable base universes exist
The system SHALL provide tradeable-first base universes for Binance spot and perps.

#### Scenario: Spot tradeable base exists
- **WHEN** `asset_type=crypto` and `universe=binance_spot_tradeable_base`
- **THEN** the system returns a list of Binance spot tickers

#### Scenario: Perp tradeable base exists
- **WHEN** `asset_type=crypto` and `universe=binance_perp_tradeable_base`
- **THEN** the system returns a list of Binance perp tickers

### Requirement: Tradeable base is quote-asset restricted
The system SHALL restrict tradeable-base tickers to an allowlist of quote assets.

#### Scenario: Quote-asset allowlist
- **GIVEN** `quote_assets=[USDT, USDC]`
- **WHEN** the tradeable base universe is built
- **THEN** all tickers end with `USDT` or `USDC` (and `.P` for perps)

### Requirement: One ticker per base
The system SHOULD pick at most one ticker per base asset.

#### Scenario: Prefer USDT
- **GIVEN** both `BASEUSDT` and `BASEUSDC` exist
- **WHEN** the universe is built
- **THEN** it includes `BASEUSDT` and not `BASEUSDC`

### Requirement: Default liquidity floors keep spot/perp sizes comparable
The system SHOULD tune default liquidity floors so spot and perp tradeable-base universes are similar in size.
