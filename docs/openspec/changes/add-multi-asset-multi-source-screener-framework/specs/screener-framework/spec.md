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

### Requirement: Multi-asset multi-timeframe scanner parity
The system SHALL execute the same screener/scanner program across multiple asset types and
timeframe sets using the same functional contract.

#### Scenario: One program, many assets
- **WHEN** a screener is configured for forex, stocks, and crypto
- **THEN** orchestration applies the same composition steps (rank, filter, strategy confirm)
- **AND** per-asset outputs are tagged with canonical run envelope columns

#### Scenario: One program, many timeframe sets
- **WHEN** a screener is configured for multiple timeframe sets
- **THEN** outputs remain comparable through `timeframe_set_id`
- **AND** matrix-ready analytics can be generated without screener-family-specific schema forks

### Requirement: Cross-asset screener parity is reviewable
The system SHALL support explicit parity review before enabling new asset families in production.

#### Scenario: Parity review across commodities, crypto, and equities
- **WHEN** maintainers assess readiness for additional asset types
- **THEN** they can verify screener parity for composition steps, output contracts,
  and matrix rendering compatibility
- **AND** any asset-specific exception is documented as a controlled gap, not an implicit fork
