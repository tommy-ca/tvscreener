## ADDED Requirements

### Requirement: Data source adapter contract
The system SHALL support multiple upstream data sources via a stable adapter interface.

#### Scenario: TradingView is a data source
- **WHEN** the system ingests screener snapshot data from TradingView
- **THEN** the data source is recorded as `source=tradingview`
- **AND** ingestion emits dataframes compatible with the Bronze stage contract

#### Scenario: Additional sources can be added without changing downstream logic
- **WHEN** a new upstream source is introduced (broker, exchange, vendor)
- **THEN** it can be integrated by implementing the adapter interface
- **AND** downstream medallion and analytics pipelines do not require source-specific branching

### Requirement: Per-source health and coverage gating
The system SHALL compute coverage/health metrics for each run and data source.

#### Scenario: Partial upstream data does not publish Silver/Gold
- **WHEN** ingestion returns partial results below a configured threshold
- **THEN** Bronze MAY be written with coverage metadata
- **AND** Silver/Gold publish is blocked for that run/unit

### Requirement: Provenance for reconciliation
The system SHALL record enough provenance to reconcile and compare data across sources.

#### Scenario: Source provenance fields exist
- **WHEN** Bronze rows are persisted
- **THEN** the system records `source`
- **AND** records a source-scoped identifier when available (e.g. `source_event_id`)

