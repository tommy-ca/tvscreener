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

### Requirement: Source-aware fetch throttling and bounded retries
The system SHALL support per-source fetch throttling and bounded retry policy for ingestion steps.

#### Scenario: Throttling is source-scoped
- **WHEN** ingestion is configured with source-specific rate limit policy
- **THEN** fetch batches are delayed according to that source policy (`min_interval_seconds`, `jitter_seconds`)
- **AND** analytics-only steps are unaffected by fetch throttling

#### Scenario: Retries are bounded for fetch steps
- **WHEN** transient fetch failures occur
- **THEN** ingestion retries failed batches with exponential backoff + jitter
- **AND** retries stop at configured max attempts for that source

### Requirement: Provenance for reconciliation
The system SHALL record enough provenance to reconcile and compare data across sources.

#### Scenario: Source provenance fields exist
- **WHEN** Bronze rows are persisted
- **THEN** the system records `source`
- **AND** records a source-scoped identifier when available (e.g. `source_event_id`)

### Requirement: Per-asset source coverage is measurable
The system SHALL support readiness assessment of source coverage by asset type.

#### Scenario: Source readiness matrix can be produced
- **WHEN** maintainers evaluate expansion to commodities, crypto, or equities
- **THEN** they can report source readiness per asset type (universe coverage, rate-limit profile,
  retry behavior, and provenance completeness)
