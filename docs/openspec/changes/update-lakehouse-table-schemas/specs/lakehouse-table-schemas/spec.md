## ADDED Requirements

### Requirement: Iceberg identifier semantics are canonical
The system SHALL use Iceberg-native naming semantics: catalog (configured), namespace, then table.

#### Scenario: Table identifiers are namespace-qualified
- **WHEN** code or docs refer to a lakehouse table
- **THEN** the identifier uses `namespace.table` (e.g. `tvscreener_gold.screener_snapshot`)
- **AND** does not bake a filesystem path into the identifier

#### Scenario: Stage-oriented namespaces are used
- **WHEN** new lakehouse tables are introduced
- **THEN** they use stage-oriented namespaces:
  - `tvscreener_bronze`
  - `tvscreener_silver`
  - `tvscreener_gold`
  - `tvscreener_product` (analytics products)
- **AND** table names are dataset names (e.g. `screener_snapshot`, `market_klines`) without stage prefixes

### Requirement: Idempotent overwrites do not emit noise warnings
The system SHOULD keep idempotent overwrite operations warning-clean.

#### Scenario: No-op delete warning is suppressed
- **GIVEN** an overwrite operation targets a partition that does not yet exist
- **WHEN** the Iceberg engine emits a no-op delete warning
- **THEN** the system suppresses only the specific warning and proceeds

### Requirement: Namespace layout scales by asset and instrument type
The system SHOULD support a naming layout that isolates schemas by asset type and instrument type.

#### Scenario: Crypto spot and perp schemas are isolated
- **WHEN** the system persists screener snapshot rows for both crypto spot and crypto perps
- **THEN** they are stored in separate Iceberg tables or namespaces so incompatible fields do not force nullable growth

#### Scenario: SQL examples include catalog when required
- **WHEN** SQL examples are provided for an engine that requires catalog qualification
- **THEN** the examples use `catalog.namespace.table` (e.g. `local.tvscreener_gold.screener_snapshot`)

### Requirement: Dataset-aware medallion schemas
The system SHALL support multiple dataset types (screener snapshots, klines, ticks, order book)
without mixing incompatible payload schemas into a single “junk drawer” table.

#### Scenario: Screener snapshots and klines use separate tables (or namespaces)
- **WHEN** the system persists TradingView screener snapshots and OHLCV bars
- **THEN** the datasets are stored in separate Iceberg tables (or separate namespaces)
- **AND** adding one dataset does not require adding nullable columns to the other dataset tables

### Requirement: Prebuilt schema packs are first-class (DBN, Cryptofeed)
The system SHALL support “schema packs” where upstream ecosystems define canonical record schemas
(e.g., Databento DBN records, Cryptofeed dtype objects), and SHALL map them onto explicit dataset tables.

#### Scenario: DBN record families map to stable dataset tables
- **WHEN** ingesting DBN-encoded market data (trades, book, instrument definitions)
- **THEN** records are mapped into **Silver** dataset tables such as `market_trades`, `market_book_l2`, `market_book_l3`, and `instrument_definitions`
- **AND** the mapping does not depend on connector-specific naming

#### Scenario: Cryptofeed dtype families map to stable dataset tables
- **WHEN** ingesting Cryptofeed-normalized updates
- **THEN** dtype objects are mapped into **Silver** dataset tables such as `market_trades`, `market_bbo`, `market_book_l2`, `market_klines`
- **AND** derivative-only dtypes (e.g. funding, open interest, liquidations) are mapped into derivative-only dataset tables

### Requirement: Derivatives datasets are modeled explicitly
The system SHALL support derivatives asset types (futures, options, perpetual swaps, CFDs) with
explicit datasets for reference/instrument metadata and derivative-only time-series.

#### Scenario: Instrument/reference data is stored separately
- **WHEN** a source provides point-in-time instrument definition updates
- **THEN** the system persists those updates into an `instrument_definitions` dataset table
- **AND** other datasets can join via stable identity (`entity_id`) and/or source instrument identifiers

#### Scenario: Derivative-only time-series do not pollute spot datasets
- **WHEN** persisting derivative-only time-series (funding rates, open interest, liquidation events)
- **THEN** they are stored in dedicated dataset tables (e.g. `deriv_funding`, `deriv_open_interest`, `deriv_liquidations`)
- **AND** spot datasets (trades/book/bars) do not gain nullable derivative-specific columns as a result

### Requirement: Shared envelope consistency
All persisted datasets SHALL carry a shared envelope/provenance contract.

#### Scenario: Shared envelope columns exist
- **WHEN** any medallion row is written
- **THEN** it includes `dataset_type`, `run_id`, `fetched_at_utc`, `asset_type`, and `source`
- **AND** includes `timeframes` and `timeframe_set_id` for timeframe-set-scoped datasets

### Requirement: TradingView screener snapshot contract is explicit
The system SHALL define and enforce the required columns for TradingView screener snapshot rows.

#### Scenario: Required TradingView identifiers exist
- **WHEN** a TradingView screener snapshot row is written to Bronze/Silver/Gold
- **THEN** it includes either `Symbol` (TradingView-qualified) or a derived `entity_id`
- **AND** it includes a price column (`Price` or canonical `PRICE`) if risk/scoring depends on it

### Requirement: Silver normalization is deterministic
Silver schemas SHALL be deterministic functions of Bronze plus normalization rules.

#### Scenario: Canonical identity columns exist in Silver
- **WHEN** Silver rows are written
- **THEN** they include `venue`, `symbol`, and `entity_id` when a source identifier exists

#### Scenario: Technical columns are canonicalized
- **WHEN** Silver rows are written with timeframe technical fields
- **THEN** technical columns use a consistent naming convention (e.g. `TREND_{tf}`, `MA_{tf}`, `OSC_{tf}`, `ROC_{tf}`)

### Requirement: Gold feature schema is explicit
Gold schemas SHALL explicitly define the score/confluence/risk outputs produced by the pipeline.

#### Scenario: Gold contains ensemble and direction
- **WHEN** Gold rows are written for opportunity screening
- **THEN** they include `ENSEMBLE_SCORE` and `DIRECTION`
- **AND** include the confluence outputs required for matrix rendering (`GRID_*`, `GRADE`, etc.)
