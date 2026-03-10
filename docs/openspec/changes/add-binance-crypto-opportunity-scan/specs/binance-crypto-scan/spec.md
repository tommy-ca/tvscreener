## ADDED Requirements

### Requirement: TradingView crypto /scan supports Binance spot + perps
The system SHALL support scanning Binance spot and perpetual instruments using TradingView's crypto `/scan` endpoint.

#### Scenario: Spot instruments are identified
- **GIVEN** `asset_type=crypto` and `venue=binance`
- **WHEN** the universe selector runs
- **THEN** it can select spot instruments where TradingView `Type=spot`

#### Scenario: Perpetual instruments are identified
- **GIVEN** `asset_type=crypto` and `venue=binance`
- **WHEN** the universe selector runs
- **THEN** it can select perpetual instruments where TradingView `Type=swap` (e.g. symbols ending with `.P`)

### Requirement: Universe selection supports top-100 by volume with filters
The system SHALL support selecting a Binance crypto universe by deterministic ranking and filters.

#### Scenario: Top 100 by volume with min thresholds
- **GIVEN** the operator requests a Binance crypto scan
- **AND** the selection constraints are:
  - `market_types = [spot, perp]`
  - `min_quote_volume_usd` is configurable; defaults:
    - spot: `2_500_000`
    - perp: `10_000_000`
  - `min_volatility_24h_pct = 3.0`
  - `top_n = 100`
- **WHEN** the universe selector runs
- **THEN** it returns at most 100 instruments ordered by `quote_volume_usd` descending
- **AND** every instrument in the returned set meets the minimum thresholds

#### Scenario: Selection type is recorded
- **WHEN** the universe selector writes `universe.json`
- **THEN** it includes a `constraints.selection` label (e.g. `top_by_volume_filtered`)

### Requirement: Universe selection supports market cap top-100
The system SHALL support selecting Binance spot/perp markets derived from the top 100 coins by market cap.

#### Scenario: Market cap top 100 then rank by trading value
- **GIVEN** the operator requests `universe=binance_spot_mcap_top100` (or perp variant)
- **WHEN** the universe selector runs
- **THEN** it derives a base-asset list from the top 100 coins by market cap
- **AND** maps those bases to Binance markets using `quote_assets` (default `USDT`, fallback `USDC`)
- **AND** it does not apply volume/volatility filters at selection time
- **AND** it persists `universe.json` with `quote_volume_usd` and `volatility_24h_pct` for later analytics filtering

#### Scenario: Volatility uses TradingView native field when available
- **GIVEN** TradingView returns a `Volatility` column for a candidate instrument
- **WHEN** the universe selector computes `volatility_24h_pct`
- **THEN** it uses TradingView's `Volatility` value
- **AND** does not rely on a derived `(High-Low)/Price` proxy

### Requirement: Opportunity scanner is shared across asset types
The system SHALL run the same opportunity scanner family for forex and Binance crypto.

#### Scenario: Same scanner family, different source
- **GIVEN** a run executes with `scanner_family=opportunity`, `asset_type=crypto`, `source=tradingview`
- **WHEN** the analytics pipeline renders the matrix view
- **THEN** the output is compatible with the existing matrix rendering contract

### Requirement: Universe membership is persisted for reproducibility
The system SHALL persist the selected universe snapshot as an artifact.

#### Scenario: Universe snapshot artifact exists
- **GIVEN** a run executes against Binance crypto
- **WHEN** the universe selector completes
- **THEN** it writes `universe.json` under `artifacts/runs/<params_hash>/`
- **AND** it includes `entity_id`, `symbol`, `instrument_type`, `quote_volume_usd`, and `volatility_24h_pct`

#### Scenario: Universe snapshot reports missing bases
- **GIVEN** the universe selector maps from a base list (e.g. market cap bases)
- **WHEN** it writes `universe.json`
- **THEN** it includes `included_bases` and `missing_bases` to quantify mapping coverage

### Requirement: Tradeable base universes exist
The system SHOULD provide Binance-first tradeable base universes for strategy development.

#### Scenario: Tradeable base uses liquidity floors
- **WHEN** the tradeable base universe is built with defaults
- **THEN** it applies a liquidity floor tuned per instrument type

## MODIFIED Requirements

### Requirement: Artifacts remain minimal but rich
The system SHOULD keep the artifacts contract minimal while preserving reproducibility.

#### Scenario: Essential artifacts still produced
- **WHEN** a Binance crypto run executes
- **THEN** it writes the essential artifacts (`run_spec.json`, `run_result.json`, results parquet, optional `matrix.txt`)
- **AND** it additionally writes `universe.json` as the minimal extra artifact needed for reproducibility
