# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: Prefect stages are composable
The extensions Prefect implementation SHALL expose composable stage tasks.

#### Scenario: Data stage is a task
- **WHEN** a run executes with `pipeline_mode=data`
- **THEN** Prefect executes a dedicated data stage task
- **AND** the task performs ingestion + feature engineering + Iceberg writes

#### Scenario: Analytics stage is a task
- **WHEN** a run executes with `pipeline_mode=analytics`
- **THEN** Prefect executes a dedicated analytics stage task
- **AND** the task reads Iceberg and writes filesystem artifacts (`*_results.parquet`, `matrix.md` when enabled)

#### Scenario: Both can be composed from stage tasks
- **WHEN** a run executes with `pipeline_mode=both` under the composed path
- **THEN** Prefect executes the data stage task first
- **AND** executes the analytics stage task second with an explicit dependency

### Requirement: Operator can keep work queues healthy
The system SHOULD provide an operator command to prune late scheduled runs so on-demand runs can execute promptly.

#### Scenario: Operator prunes late scheduled runs
- **GIVEN** a work queue has accumulated scheduled runs that are already late
- **WHEN** the operator runs `tvscreener-prefectctl prune-late --work-queue default --older-than-minutes N`
- **THEN** the tool cancels late scheduled flow runs

### Requirement: Health checks use Prefect API client
Operator health checks SHOULD use the Prefect Python API client.

#### Scenario: Check uses Prefect client
- **WHEN** the operator runs `tvscreener-prefectctl check`
- **THEN** it uses `prefect.client.orchestration.get_client` and does not shell out to Prefect CLI

### Requirement: Server control is best-effort
The system MAY provide a wrapper for starting/stopping the Prefect server, but it MUST surface failures clearly.

#### Scenario: Server start fails cleanly
- **GIVEN** a Prefect server is already running on the configured port
- **WHEN** the operator runs `tvscreener-prefectctl server start --background`
- **THEN** the command exits non-zero and prints an actionable error

### Requirement: Operators can inspect artifacts via API
The system SHOULD provide a helper to list Prefect artifacts for auditing.

#### Scenario: Operator lists matrix artifacts
- **WHEN** the operator runs `tvscreener-prefectctl artifacts --type markdown --key-like tvscreener-matrix-%`
- **THEN** the tool lists recent matrix artifacts with ids and keys
