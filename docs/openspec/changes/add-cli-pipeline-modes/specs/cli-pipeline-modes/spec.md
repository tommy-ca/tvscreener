## ADDED Requirements

### Requirement: CLI supports pipeline modes
The system SHALL allow running data and analytics pipelines independently via the CLI.

#### Scenario: Data-only run writes Iceberg
- **WHEN** the user runs `tvscreener-scan --pipeline data`
- **THEN** the system fetches upstream data and persists to Iceberg
- **AND** the run does not depend on any query engine backend

#### Scenario: Analytics-only run reads Iceberg and renders matrix
- **WHEN** the user runs `tvscreener-scan --pipeline analytics --matrix`
- **THEN** the system queries Iceberg tables and renders the matrix view
- **AND** the run does not fetch upstream data

#### Scenario: Both mode runs data then analytics
- **WHEN** the user runs `tvscreener-scan --pipeline both`
- **THEN** the system executes the data pipeline first
- **AND** then executes the analytics pipeline against the persisted Iceberg outputs

### Requirement: Strategy scanning is an analytics pipeline
The strategy scanner SHALL be runnable from Iceberg-backed data without writing medallion tables.

#### Scenario: Strategy analytics runs from `signals_latest`
- **WHEN** the user runs `tvscreener-scan --scanner strategy --pipeline analytics`
- **THEN** the system loads the required Gold columns from `tvscreener.signals_latest`
- **AND** computes strategy signals in-memory
- **AND** renders the same matrix view style as today

