## ADDED Requirements

### Requirement: Canonical vocabulary exists
The project SHALL define a single, canonical vocabulary for pipeline stages, lakehouse tables, orchestration objects,
and artifacts.

#### Scenario: Docs use canonical terms
- **WHEN** OpenSpec docs refer to orchestration
- **THEN** they use Prefect-native nouns: flow, deployment, work pool, work queue, worker, flow run, task run

#### Scenario: Docs describe pipeline stages consistently
- **WHEN** OpenSpec docs describe pipeline stages
- **THEN** they map `pipeline_mode` to canonical meanings:
  - `data`: ingestion + feature engineering + Iceberg writes
  - `analytics`: reporting + Iceberg reads + artifact writes
  - `both`: `data` then `analytics`

### Requirement: Interfaces avoid random naming
User-facing identifiers SHALL be deterministic.

#### Scenario: Run identifiers are deterministic
- **WHEN** a pipeline run is requested
- **THEN** it uses `params_hash` as a stable run identifier
- **AND** filesystem artifacts are written under `artifacts/runs/<params_hash>/`

#### Scenario: Prefect artifacts are deterministic
- **WHEN** Prefect publishes artifacts for a run
- **THEN** artifact keys are derived from `PipelineRunSpec` (not Prefect-generated whimsical names)

#### Scenario: Health checks do not rely on whimsical names
- **WHEN** the operator runs `tvscreener-prefectctl check`
- **THEN** it reports scheduled runs using `flow_run_id` (not the Prefect-assigned run name)

### Requirement: Extensions wrappers are Prefect-native
Extensions tooling SHALL not shell out to the Prefect CLI.

#### Scenario: Wrappers use Prefect Python APIs
- **WHEN** an operator uses extensions Prefect helpers (`tvscreener-prefectctl`, `tvscreener-prefectctl check`)
- **THEN** they use Prefect Python APIs (client + worker classes) instead of subprocess calls
