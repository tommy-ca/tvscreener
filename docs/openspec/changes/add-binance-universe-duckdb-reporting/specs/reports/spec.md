# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: DuckDB reports can be generated for Binance universes
The system SHALL generate structured reports for Binance universes.

#### Scenario: Report command writes artifacts
- **WHEN** the operator runs `tvscreener-scan report binance-universes`
- **THEN** the system writes `report.json` and `report.md` under `artifacts/reports/binance-universes/<timestamp>/`

#### Scenario: Report includes summary metrics
- **WHEN** a report is generated
- **THEN** it includes per-universe liquidity and volatility distribution summaries

#### Scenario: Report includes volume distributions and per-asset overview
- **WHEN** a report is generated
- **THEN** it includes per-universe quote-volume percentiles
- **AND** it includes a per-universe table of top assets by `quote_volume_usd`

#### Scenario: Report writes full per-asset volume tables
- **WHEN** a report is generated
- **THEN** it writes parquet artifacts with ticker-level and base-level volumes per universe

#### Scenario: Report surfaces risky tradeable assets
- **WHEN** a report is generated
- **THEN** it writes a `risky_assets` section listing non-mcap-top100 bases present in tradeable universes (when `history_days` is available)

#### Scenario: Report includes excluded risky counts
- **WHEN** a report is generated
- **THEN** the per-universe summary includes the count of `excluded_risky` candidates (when present in `universe.json`)

#### Scenario: Report includes strategy readiness table
- **WHEN** a report is generated
- **THEN** it includes a strategy readiness table for `tradeable_base` and `tradeable_mcap_cs` universes with a default-ready boolean and supporting metrics

#### Scenario: Report includes scanner readiness table
- **WHEN** a report is generated
- **THEN** it includes a scanner readiness table with heuristic checks for opportunity and strategy scanners

#### Scenario: Report breaks down spot universes by quote and volume
- **WHEN** a report is generated
- **THEN** it includes a spot-only breakdown grouped by `universe` and `quote_asset` including volume distribution metrics

#### Scenario: Review pipeline produces actionable audit artifacts
- **GIVEN** the operator wants to audit strategy readiness
- **WHEN** `tvscreener-scan review binance-universes` runs
- **THEN** the resulting report provides enough information to validate quote purity, volume distributions, and spot/perp parity

#### Scenario: Report includes top100 diagnostics
- **WHEN** a report is generated
- **THEN** it includes a diagnostics table for `binance_{spot,perp}_top100` showing candidate counts through quote/volume/exclusion/dedup steps

#### Scenario: Audit flags underfilled top-N universes
- **WHEN** `audit binance-universes` runs
- **THEN** it flags an error if `binance_{spot,perp}_top100` returns fewer than 100 instruments

#### Scenario: Report includes overlap comparisons
- **WHEN** a report is generated
- **THEN** it includes overlap comparisons across universes by ticker and by base

#### Scenario: Report highlights spot top100 quote composition
- **WHEN** a report is generated
- **THEN** it includes a per-quote summary for `binance_spot_top100` including duplicate-base counts and sample tickers

#### Scenario: Report compares spot vs perp parity
- **WHEN** a report is generated
- **THEN** it includes a parity view comparing spot vs perp universes by family, including base overlap and median liquidity/volatility
