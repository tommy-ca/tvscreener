## ADDED Requirements

### Requirement: Lakehouse-first auditing
The system SHALL treat Iceberg medallion tables (`tvscreener.bronze`, `tvscreener.silver`,
`tvscreener.gold`) as the canonical source of truth for audits and downstream validation.

#### Scenario: Audit uses Iceberg identifiers
- **WHEN** an operator runs an audit query
- **THEN** the query targets an Iceberg table identifier (e.g. `tvscreener.gold`)
- **AND** the audit does not require any repository-local parquet/text snapshot files

### Requirement: Optional on-disk snapshots are explicit
The system SHALL support optional on-disk snapshot exports, but snapshots MUST NOT be required for
correctness or for reproducing audit conclusions.

#### Scenario: No snapshots by default
- **WHEN** an operator runs a scan using default settings
- **THEN** the system writes medallion outputs to Iceberg tables
- **AND** no on-disk snapshot output path is assumed or implied

#### Scenario: Operator requests a snapshot explicitly
- **WHEN** an operator supplies an output path for a snapshot export
- **THEN** the system writes that snapshot to the requested path
- **AND** the audit record MUST still reference the Iceberg snapshot IDs for canonical provenance

### Requirement: Reproducible audit recordkeeping
The audit process SHALL record enough metadata to reproduce an audit against the same lakehouse
snapshots.

#### Scenario: Audit record entry includes provenance
- **WHEN** an operator records an audit session
- **THEN** the record includes `run_id`, `fetched_at_utc`, and `timeframe_set_id` (when available)
- **AND** includes Iceberg `snapshot_id` values for Bronze/Silver/Gold (or equivalent provenance)
- **AND** includes the exact SQL used for the spot checks

### Requirement: Multi-asset identity columns
The system SHALL produce canonical identity columns for persisted Silver/Gold rows to support
multi-asset overwrite scoping and joins.

#### Scenario: Identity columns exist on standardized data
- **WHEN** the pipeline writes Silver and Gold outputs
- **THEN** rows include `asset_type`
- **AND** include `entity_id`, `symbol`, and `venue` when a source symbol is available

### Requirement: Multi-asset overwrite safety
The system SHALL avoid deleting unrelated entities when overwriting partitions for a partial scan.

#### Scenario: Overwrite is scoped to entity keys
- **WHEN** the pipeline overwrites Silver/Gold partitions
- **THEN** the overwrite filter includes partition keys AND an entity identifier (prefer `entity_id`)
- **AND** scanning a subset of entities does not remove other entities in the same partition

### Requirement: Documentation distinguishes current vs proposed behavior
The system documentation SHALL clearly separate “current implementation status” from “proposed
architecture” to prevent operators from following non-existent workflows.

#### Scenario: Multi-asset plan includes current status
- **WHEN** an operator reads the multi-asset design plan
- **THEN** it includes a “Current implementation status” section
- **AND** any outdated “current state audit” claims are corrected or annotated

