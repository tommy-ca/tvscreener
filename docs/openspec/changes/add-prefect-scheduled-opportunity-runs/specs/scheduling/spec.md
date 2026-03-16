## ADDED Requirements

### Requirement: Scheduled runs cover key universes
The system SHOULD support scheduled execution of opportunity data pipelines for:
- forex majors/minors
- Binance crypto spot/perp majors/minors
- market risk proxy basket

#### Scenario: Prefect cron triggers periodic batch runs
- **GIVEN** a Prefect deployment exists for `workflows/prefect/run_batch.py:run_batch`
- **WHEN** cron schedules are registered
- **THEN** Prefect creates flow runs periodically with deterministic `PipelineRunSpec` artifacts under `artifacts/runs/`

### Requirement: Schedules can run via Prefect workers
The system SHOULD support registering deployments against a Prefect work pool so `prefect worker start --pool <pool>` can execute scheduled runs.

#### Scenario: Work-pool deployment runs on a worker
- **GIVEN** a Prefect work pool exists (e.g. `tvscreener`)
- **AND** deployments are created with `work_pool_name=tvscreener`
- **AND** deployments set `job_variables.working_dir` to the repo root for file-path entrypoints
- **WHEN** `prefect worker start --pool tvscreener` is running
- **THEN** scheduled flow runs are picked up and executed by the worker

### Requirement: Scheduled data runs fail on persistence errors
Scheduled `data` runs SHOULD NOT report success when Iceberg persistence fails.

#### Scenario: Iceberg write fails during a scheduled data run
- **GIVEN** a scheduled Prefect run executes the `data` pipeline
- **WHEN** an Iceberg write fails (e.g. schema drift)
- **THEN** the run fails (non-success) so operators can react

### Requirement: Data-first scheduling does not refresh analytics artifacts
When scheduling `pipeline_mode=data`, matrix outputs and analytics parquet artifacts are not expected to update.

#### Scenario: Operator expects a fresh matrix after a data-only schedule
- **GIVEN** the latest scheduled run executed `pipeline_mode=data`
- **WHEN** an operator needs an updated matrix view
- **THEN** they run `pipeline_mode=analytics` (or schedule `pipeline_mode=both`) to regenerate `matrix.txt` and analytics outputs
