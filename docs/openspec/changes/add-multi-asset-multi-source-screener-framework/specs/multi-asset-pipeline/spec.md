## ADDED Requirements

### Requirement: Multi-asset medallion contract
The system SHALL persist medallion outputs in a way that is correct across multiple asset types.

#### Scenario: Identity keys are available for all assets
- **WHEN** Silver or Gold rows are persisted
- **THEN** rows include `asset_type`
- **AND** include `entity_id` when a per-entity identifier is available (e.g. TradingView Symbol, forex PAIR)

#### Scenario: Overwrite scoping is not forex-specific
- **WHEN** a scan overwrites Silver/Gold partitions for a subset of entities
- **THEN** the overwrite scope includes partition keys AND `entity_id` (preferred)
- **AND** unrelated entities in the same partition are not removed

### Requirement: Run envelope completeness
The system SHALL attach a run envelope to all persisted stage rows for auditability and replay.

#### Scenario: Required run envelope columns exist
- **WHEN** Bronze/Silver/Gold rows are written
- **THEN** each row includes `run_id`, `fetched_at_utc`, and `timeframe_set_id`
- **AND** includes `source` and `scanner_family` when applicable

#### Scenario: Reproducibility fields exist
- **WHEN** a run is persisted
- **THEN** the system records a `code_version` identifier and a stable `params_hash`

### Requirement: Multi-timeframe contract
The system SHALL treat multi-timeframe configuration as a first-class dimension of the pipeline.

#### Scenario: Timeframe set identity exists for wide-form tables
- **WHEN** a scan persists wide-form Silver/Gold rows (timeframe-as-columns)
- **THEN** the run envelope includes `timeframes` and `timeframe_set_id`

#### Scenario: Long-form tables can represent variable timeframe sets
- **WHEN** a pipeline uses long-form storage
- **THEN** rows include a `timeframe` column in addition to `timeframe_set_id`
- **AND** analytics can aggregate across `timeframe` to produce matrix-ready outputs

### Requirement: Product tables for scalable analytics
The system SHALL provide small, curated analytics output tables to avoid scanning historical feature tables for common queries.

#### Scenario: Latest table is queryable without full history scans
- **WHEN** an operator queries the latest signals
- **THEN** a “latest” table (e.g. `tvscreener.signals_latest`) provides latest-per-entity rows
- **AND** it is partitioned/indexed for fast retrieval by `asset_type` and `timeframe_set_id`

### Requirement: Universe membership is modeled explicitly
The system SHALL model universes as membership data rather than as storage/partition axes.

#### Scenario: Universe selection is reproducible
- **WHEN** a run is executed with a universe selector (e.g. majors/minors)
- **THEN** the resolved universe membership can be reproduced or recorded (run metadata or table)

