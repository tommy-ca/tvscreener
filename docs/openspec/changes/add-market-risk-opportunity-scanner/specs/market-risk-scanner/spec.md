## ADDED Requirements

### Requirement: Market risk scanner uses opportunity pipelines
The system SHALL support running a market risk scanner through the same `data` and `analytics` pipelines as other opportunity scans.

#### Scenario: Futures risk basket persists
- **GIVEN** `scanner=opportunity`, `asset_type=futures`, and `pairs={ES1!, NQ1!, VX1!}`
- **WHEN** the operator runs `--pipeline data`
- **THEN** Iceberg `tvscreener.signals_latest` contains rows for each requested futures ticker with a consistent `entity_id`

#### Scenario: DXY persists
- **GIVEN** `scanner=opportunity`, `asset_type=stock`, and `pairs={TVC:DXY}`
- **WHEN** the operator runs `--pipeline data`
- **THEN** Iceberg `tvscreener.signals_latest` contains a row for DXY with a consistent `entity_id`

#### Scenario: Analytics pipeline rerenders matrix from Iceberg
- **GIVEN** Iceberg contains recent market risk rows
- **WHEN** the operator runs `--pipeline analytics --matrix`
- **THEN** the Confluence Matrix renders for the market risk basket and is ordered by descending opportunity rank (`ENSEMBLE_SCORE`, then `GRID_ALIGNED`)

### Requirement: Basket is deterministic and auditable
The system SHALL define a deterministic market risk basket and persist the resolved symbols in a universe snapshot artifact.

#### Scenario: Basket resolves to the expected symbols
- **GIVEN** the market risk overlay is configured
- **WHEN** the overlay is executed
- **THEN** the resolved tickers include `CME_MINI:ES1!`, `CME_MINI:NQ1!`, `CBOE:VX1!`, and `TVC:DXY`
