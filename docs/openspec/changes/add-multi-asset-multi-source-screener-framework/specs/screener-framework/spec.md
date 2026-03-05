## ADDED Requirements

### Requirement: Screener family registry
The system SHALL support multiple screener families (ranking, filters, strategy-specific) via a registry.

#### Scenario: Opportunity and strategy are first-class families
- **WHEN** a scan is executed
- **THEN** the run is tagged with `scanner_family` (e.g. `opportunity`, `strategy`)
- **AND** the pipeline can route to the corresponding screener implementation

#### Scenario: New families can be added
- **WHEN** a new screener family is implemented
- **THEN** it can be registered without modifying core orchestration logic

### Requirement: Screener composition primitives
The system SHALL allow composing screening logic from reusable steps.

#### Scenario: Rank then filter
- **WHEN** a scan uses a ranking step followed by a filter step
- **THEN** the output is deterministic and reproducible from Iceberg snapshots

#### Scenario: Strategy confirmation uses shared features
- **WHEN** a strategy-specific screener runs after a ranking stage
- **THEN** it reuses canonical identity keys and shared feature columns from Gold
- **AND** it can reference per-timeframe features and cross-timeframe aggregates via the analytics contract

### Requirement: Presentation contract for matrix view
The system SHALL define a stable “matrix view contract” for any screener output that supports matrix rendering.

#### Scenario: Matrix renderer requirements are documented
- **WHEN** a screener opts into matrix rendering
- **THEN** its output includes canonical columns needed for rendering (e.g. `PAIR` or `symbol`, `DIRECTION`, confluence counters)
- **AND** those columns are derivable from Iceberg-backed analytics outputs (not ad-hoc files)

### Requirement: Screener outputs are backend-agnostic
The system SHALL allow the same screening program to be evaluated using different analytics backends.

#### Scenario: DuckDB and Narwhals are interchangeable for analytics steps
- **WHEN** an operator uses SQL or Narwhals expressions to filter/rank
- **THEN** the analytics pipeline can execute those steps using the configured backend
- **AND** the resulting dataset remains compatible with rendering and export contracts

