## ADDED Requirements

### Requirement: Opportunity scanning supports crypto majors/minors
The system SHALL support running the opportunity scanner over Binance crypto majors/minors universes.

#### Scenario: Spot majors opportunity scan
- **GIVEN** `scanner=opportunity`, `asset_type=crypto`, `instrument_type=spot`
- **WHEN** the operator selects `--universe majors`
- **THEN** symbols are resolved from `binance_spot_majors`

#### Scenario: Perp minors opportunity scan
- **GIVEN** `scanner=opportunity`, `asset_type=crypto`, `instrument_type=perp`
- **WHEN** the operator selects `--universe minors`
- **THEN** symbols are resolved from `binance_perp_minors`

### Requirement: Opportunity scanner uses the same analytics contract
The system SHALL use the same opportunity analytics pipeline and matrix rendering contract for forex and crypto.

#### Scenario: Analytics-only rerender
- **GIVEN** a prior data run exists in Iceberg
- **WHEN** the operator runs with `--pipeline analytics`
- **THEN** the matrix view renders without refetching upstream data

### Requirement: Run metadata supports audit queries
The system SHOULD persist `instrument_type` for each run in `tvscreener.runs`.

#### Scenario: Crypto run records instrument_type
- **GIVEN** `asset_type=crypto`
- **WHEN** a run record is written
- **THEN** the run record includes `instrument_type` (`spot` or `perp`)

#### Scenario: Local runner writes run metadata
- **GIVEN** the operator runs with `--runner local`
- **WHEN** the scan completes
- **THEN** a row is appended to `tvscreener.runs`

#### Scenario: Matrix view can be rendered for majors/minors
- **GIVEN** `scanner=opportunity`, `asset_type=crypto`, and `universe=majors` (or `minors`)
- **WHEN** the operator runs with `--matrix`
- **THEN** the matrix view renders (even when the result set is empty)

#### Scenario: Crypto matrix view matches forex confluence format
- **GIVEN** `asset_type=crypto` and a non-empty opportunity result set
- **WHEN** `--matrix` is used
- **THEN** the output uses the Confluence Matrix format (TREND/MA/OSC/ROC across timeframes + Grid + Grade)

#### Scenario: Matrix view shows readable pair labels for crypto
- **GIVEN** a crypto universe returns fully-qualified symbols like `BINANCE:BTCUSDT`
- **WHEN** the matrix view is rendered
- **THEN** the view includes a readable `PAIR` label with the venue prefix stripped (e.g., `BTCUSDT`)

### Requirement: Forex parity for majors/minors matrix renders
The system SHOULD render non-empty opportunity matrices for forex and crypto majors/minors when Iceberg has recent data.

#### Scenario: Forex majors/minors supports data then analytics
- **GIVEN** `asset_type=forex` and `universe=majors` (or `minors`)
- **WHEN** the operator runs `--pipeline data` and later `--pipeline analytics --matrix`
- **THEN** the matrix view renders and includes the expected confluence columns

#### Scenario: Pipeline modes are valid for majors/minors
- **GIVEN** `asset_type=crypto` and `universe=majors` (or `minors`)
- **WHEN** the operator runs with `--pipeline data` and later `--pipeline analytics`
- **THEN** both runs complete successfully

#### Scenario: Matrix view preserves ranked order
- **GIVEN** `scanner=opportunity` and a non-empty result set
- **WHEN** the operator runs `--pipeline analytics --matrix`
- **THEN** the matrix rows are rendered in descending opportunity rank order (highest `ENSEMBLE_SCORE`, then `GRID_ALIGNED`)
