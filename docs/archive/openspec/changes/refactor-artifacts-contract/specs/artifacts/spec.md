# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: Artifacts are minimal and engine-agnostic
The system SHALL write run artifacts under an engine-agnostic base directory.

#### Scenario: Canonical base directory for any runner
- **GIVEN** a pipeline run executes via local runner, Prefect runner, or another workflow engine
- **WHEN** artifacts are written
- **THEN** they are written under `artifacts/runs/<params_hash>/` by default

### Requirement: Exactly one run result JSON exists per run
The system SHALL produce a single `run_result.json` for any `pipeline_mode`.

#### Scenario: Data-only run still writes run_result.json
- **GIVEN** a run executes with `pipeline_mode=data`
- **WHEN** it completes
- **THEN** `artifacts/runs/<params_hash>/run_result.json` exists
- **AND** it does not require a separate `run_result_data.json` to interpret success/failure

#### Scenario: Analytics-only run writes results_path
- **GIVEN** a run executes with `pipeline_mode=analytics`
- **WHEN** it completes successfully
- **THEN** `run_result.json` includes a `results_path` pointing to `<scanner_family>_results.parquet`

### Requirement: Artifacts are deterministic and self-describing
The system SHALL make artifacts discoverable without logs.

#### Scenario: Consumers can locate outputs from JSON only
- **GIVEN** a machine consumer reads `run_result.json`
- **WHEN** it needs to find emitted products
- **THEN** it can locate the results parquet (if any) and matrix text (if any) from paths in the JSON

### Requirement: Matrix text capture is optional
The system SHALL only write `matrix.txt` when matrix rendering is requested.

#### Scenario: Matrix requested persists matrix.txt
- **GIVEN** `matrix=true` for an analytics run
- **WHEN** the run completes
- **THEN** `artifacts/runs/<params_hash>/matrix.txt` exists

#### Scenario: Matrix not requested does not persist matrix.txt
- **GIVEN** `matrix` is unset or false
- **WHEN** the run completes
- **THEN** no `matrix.txt` is written

## MODIFIED Requirements

### Requirement: Prefect artifacts remain backwards compatible
During migration, the system SHOULD support `artifacts/prefect/<params_hash>/` as a legacy alias.

#### Scenario: Legacy base directory still works
- **GIVEN** an operator configures `--artifacts-dir artifacts/prefect`
- **WHEN** a run executes
- **THEN** artifacts are written successfully under the requested base directory
