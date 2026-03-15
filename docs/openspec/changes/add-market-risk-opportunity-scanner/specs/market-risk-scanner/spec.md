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

#### Scenario: Named universe resolves proxy basket
- **GIVEN** `asset_type=stock` and `universe=market_risk`
- **WHEN** the operator runs without passing `--pairs`
- **THEN** the resolved tickers equal `AMEX:SPY`, `NASDAQ:QQQ`, `TVC:VIX`, and `TVC:DXY`

### Requirement: Market risk overlay produces non-null factors
The system SHOULD select risk proxy symbols that populate `TREND/MA/OSC/ROC` factor inputs across timeframes.

#### Scenario: Proxies yield non-null factor columns
- **GIVEN** the market risk overlay uses proxy symbols
- **WHEN** the operator runs `--pipeline analytics --matrix`
- **THEN** the underlying factor columns for each instrument include non-null values for `TREND_{tf}`, `MA_{tf}`, `OSC_{tf}`, and `ROC_{tf}`
