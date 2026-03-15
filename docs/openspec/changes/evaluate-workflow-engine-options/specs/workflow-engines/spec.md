## ADDED Requirements

### Requirement: Workflow engine can run `PipelineRunSpec` deterministically
The system SHALL be able to submit a scan as an immutable `PipelineRunSpec` payload and run it without mutating parameters.

#### Scenario: Spec payload is the single source of truth
- **GIVEN** a `PipelineRunSpec` JSON payload exists
- **WHEN** a workflow engine executes a run
- **THEN** the engine uses the payload as the only run parameters (no hidden defaults)

### Requirement: Workflow engine produces artifacts for audit
The system SHALL persist run artifacts to a filesystem path keyed by `params_hash`.

#### Scenario: Matrix artifact is saved when `--matrix` is enabled
- **GIVEN** `PipelineRunSpec.matrix=true`
- **WHEN** a run completes
- **THEN** `matrix.txt` is written under `artifacts/runs/<params_hash>/matrix.txt`

### Requirement: Operational footprint matches environment
The chosen engine SHOULD align with the deployment environment.

Notes:
- If the engine license is copyleft (GPL/AGPL), the system MUST confirm distribution/compliance requirements before adoption.
