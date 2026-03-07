## ADDED Requirements

### Requirement: Analytics pipelines are separate from data pipelines
The system SHALL separate canonical data production (Iceberg medallion) from analytics production
(rankings, strategy outputs, reporting tables).

#### Scenario: Analytics does not block canonical persistence
- **WHEN** an analytics query fails (SQL error, binder error, backend limitation)
- **THEN** medallion persistence to Iceberg remains correct and complete for that run

### Requirement: Pluggable query backends
The system SHALL support running analytics pipelines against Iceberg tables using a pluggable query
backend contract.

#### Scenario: DuckDB backend (default)
- **WHEN** the operator runs ad-hoc SQL queries
- **THEN** DuckDB can query Iceberg identifiers (materialized to Arrow as needed)

#### Scenario: Alternate backend (future)
- **WHEN** a different backend is configured (e.g. Polars lazy, Spark, Trino)
- **THEN** the analytics pipeline uses that backend without changing the pipeline semantics

### Requirement: Multi-timeframe analytics patterns
The system SHALL support multi-timeframe analytics that can compute both per-timeframe features and
cross-timeframe aggregates.

#### Scenario: Per-timeframe analytics
- **WHEN** an operator queries features for a given timeframe
- **THEN** results can be filtered by `timeframe` (long-form) or by timeframe columns (wide-form)

#### Scenario: Cross-timeframe aggregate output (matrix-ready)
- **WHEN** an analytics pipeline produces a “matrix-ready” output
- **THEN** it aggregates across timeframes into stable columns used by the matrix renderer
- **AND** the output is persisted as an analytics product table (e.g. `signals_batch`, `signals_latest`)

### Requirement: Functional-first analytics delivery
The system SHALL prioritize functional parity and correctness of analytics outputs over optimization
work during initial multi-asset, multi-timeframe rollout.

#### Scenario: FR acceptance before NFR tuning
- **WHEN** planning analytics implementation work
- **THEN** required product outputs and correctness checks are completed first
- **AND** optimization tasks (performance/cost/observability refinements) are explicitly scheduled after FR completion

#### Scenario: NFR rollout is guarded by FR regression checks
- **WHEN** non-functional work is introduced after FR baseline completion
- **THEN** core FR contract tests (multi-asset identity, deterministic fan-out, analytics product-table outputs)
  remain passing
- **AND** NFR changes do not alter functional output contracts for `signals_latest`/`signals_batch`
