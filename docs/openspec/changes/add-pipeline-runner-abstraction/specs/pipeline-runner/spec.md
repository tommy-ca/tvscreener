## ADDED Requirements

### Requirement: Pipeline run specs are serializable and stable-hashable
The system SHALL represent pipeline executions as a JSON-serializable `PipelineRunSpec`.

#### Scenario: Spec can be exported and replayed
- **WHEN** a run is initiated via CLI or external engine
- **THEN** the request can be represented as a `PipelineRunSpec`
- **AND** the spec can be replayed later to reproduce the same logical run

#### Scenario: Spec includes a stable params hash
- **WHEN** a `PipelineRunSpec` is created
- **THEN** it includes `params_hash` derived from a canonical serialization of user inputs
- **AND** two specs with identical semantics have identical `params_hash`

### Requirement: Workflow-engine integration remains lightweight and engine-agnostic
The system SHALL support workflow-engine integration without introducing workflow-engine dependencies in the core
library package.

#### Scenario: Core install does not require engine dependencies
- **WHEN** a user installs the base `tvscreener` package
- **THEN** it does not require installing Dagster/Prefect/Temporal/Airflow/Argo SDKs
- **AND** workflow-engine adapters, if provided, live outside the core library package (e.g. an extensions distribution)

#### Scenario: Exported spec can be used as engine run configuration
- **WHEN** `--runner export` is used
- **THEN** the output is valid JSON for `PipelineRunSpec`
- **AND** the JSON is sufficient to parameterize an engine run without requiring interactive CLI flags
- **AND** an engine wrapper can use `params_hash` as an idempotency key / cache key

#### Scenario: Export runner can write to a file
- **WHEN** `--runner export --spec-out spec.json` is used
- **THEN** the system writes the `PipelineRunSpec` JSON to `spec.json`
- **AND** does not execute the pipeline itself

### Requirement: Pipeline execution is delegated to a runner
The system SHALL support pluggable runners for executing pipeline specs.

#### Scenario: Local runner executes in-process
- **WHEN** `--runner local` is selected
- **THEN** the system executes the pipeline synchronously in the current process

#### Scenario: Export runner produces a spec for external engines
- **WHEN** `--runner export` is selected
- **THEN** the system outputs `PipelineRunSpec` JSON for submission to an external workflow engine
- **AND** does not execute the pipeline itself

### Requirement: Analytics-only execution is read-only
Analytics pipelines SHALL NOT mutate Iceberg tables unless explicitly modeled as analytics products.

#### Scenario: Analytics-only does not change `signals_latest`
- **WHEN** an analytics-only run renders the matrix view from Iceberg
- **THEN** `tvscreener.signals_latest` `max(fetched_at_utc)` remains unchanged by that run

### Requirement: Analytics outputs include a matrix markdown artifact
Analytics pipelines SHALL render a human-readable matrix view.

#### Scenario: Analytics writes matrix markdown
- **WHEN** an analytics run completes successfully
- **THEN** it writes `matrix.md` under the run artifacts directory
