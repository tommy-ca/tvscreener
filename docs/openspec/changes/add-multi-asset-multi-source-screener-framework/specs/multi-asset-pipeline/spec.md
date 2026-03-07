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

#### Scenario: Batch and long-form products are materialized
- **WHEN** Gold outputs are persisted for a run
- **THEN** a batch product table (e.g. `tvscreener.signals_batch`) is materialized for matrix/scanner consumption
- **AND** when long-form output is enabled, a long-form table (e.g. `tvscreener.signals_long`) is materialized with `timeframe` as a first-class column

### Requirement: Universe membership is modeled explicitly
The system SHALL model universes as membership data rather than as storage/partition axes.

#### Scenario: Universe selection is reproducible
- **WHEN** a run is executed with a universe selector (e.g. majors/minors)
- **THEN** the resolved universe membership can be reproduced or recorded (run metadata or table)

### Requirement: Multi-dimensional fan-out contract
The system SHALL support deterministic run fan-out across asset types, universes, timeframe sets,
and scanner families.

#### Scenario: Batch expansion is deterministic
- **WHEN** a batch definition is expanded into run specs
- **THEN** each run envelope is uniquely identified by `asset_type`, `timeframe_set_id`,
  `scanner_family`, and universe shard identity
- **AND** each run has a stable `params_hash` that is reproducible from the same inputs

#### Scenario: Batch expansion order is deterministic
- **WHEN** the same matrix batch definition is expanded repeatedly
- **THEN** the resulting run list preserves deterministic ordering
- **AND** the ordered set of `params_hash` values is stable across runs

#### Scenario: Asset/timeframe fan-out is isolated
- **WHEN** one fan-out unit fails
- **THEN** unrelated asset types or timeframe sets can still complete and publish per contract

### Requirement: Asset-type expansion readiness is auditable
The system SHALL provide a repeatable readiness audit process before enabling new asset types at scale.

#### Scenario: Readiness audit for commodities, crypto, and equities
- **WHEN** maintainers plan to expand to additional asset families
- **THEN** they can evaluate readiness against a checklist covering identity, ingestion, analytics,
  and orchestration contracts
- **AND** each target asset type is marked as ready, ready-with-gaps, or blocked with explicit actions

#### Scenario: Expansion prep gates before deferred NFR execution
- **WHEN** readiness classification includes `ready-with-gaps` or `blocked` asset families
- **THEN** expansion preparation tasks are executed first (strategy parity, selector semantics,
  ticker normalization/validation)
- **AND** deferred NFR work resumes only after preparation gates are complete
