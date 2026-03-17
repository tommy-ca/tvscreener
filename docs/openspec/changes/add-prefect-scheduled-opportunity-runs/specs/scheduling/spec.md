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

### Requirement: Workers run against a local repo checkout
For Prefect `process` workers, scheduled deployments SHOULD assume the repo is already present on the worker machine.

#### Scenario: Worker machine does not have the repo
- **GIVEN** a Prefect `process` worker is running
- **AND** the deployment uses a file-path entrypoint like `workflows/prefect/run_batch.py:run_batch`
- **WHEN** the configured `job_variables.working_dir` does not exist on the worker machine
- **THEN** the run fails early (import/entrypoint failure)
- **AND** operators provision the repo on the worker host (Prefect does not clone code for `process` workers)

### Requirement: Scheduled deployments pass stable run parameters
Scheduled deployments SHOULD provide stable parameters for batch execution.

#### Scenario: Deployment uses the repo defaults
- **GIVEN** a deployment is created for `workflows/prefect/run_batch.py:run_batch`
- **WHEN** it is applied by `workflows/prefect/deploy_schedules.py`
- **THEN** the parameters include:
  - `batch_path` (required)
  - `artifacts_dir` (default `artifacts/runs`)
  - `data_concurrency` (default `1`)
  - `analytics_concurrency` (default `8`)
  - `rate_limit` (enabled; min interval + jitter)
  - `skip_existing` (default `False`)

### Requirement: Prefect server readiness is gated
Operators SHOULD wait for the Prefect API to be ready before applying deployments or creating flow runs.

#### Scenario: Server is starting up
- **GIVEN** the Prefect server has just been started
- **WHEN** an operator attempts to apply schedules or trigger deployments immediately
- **THEN** transient API failures (e.g. `503`) may occur
- **AND** operators SHOULD gate on `GET /api/ready` before proceeding

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

### Requirement: Analytics rerenders are auditable
When rerendering analytics (e.g. with `--matrix`), the system SHOULD write a matrix artifact and append a row to `tvscreener.runs`.

#### Scenario: Operator rerenders a matrix from fresh data
- **GIVEN** the latest successful `pipeline_mode_executed='data'` run is recent
- **WHEN** the operator runs `pipeline_mode=analytics` with `--matrix`
- **THEN** `artifacts/runs/<params_hash>/matrix.txt` is written
- **AND** a `pipeline_mode_executed='analytics'` row is appended to `tvscreener.runs`

### Requirement: Run metadata persistence can be strict
When strict persistence is enabled, failing to append `tvscreener.runs` SHOULD fail the run.

#### Scenario: Strict persistence blocks silent metadata loss
- **GIVEN** `TVSCREENER_STRICT_PERSIST=1`
- **WHEN** `tvscreener.runs` cannot be appended
- **THEN** the run fails (non-success)

### Requirement: `params_hash` is deterministic
The system SHOULD derive a deterministic `params_hash` from a normalized `PipelineRunSpec` to make artifacts content-addressed.

#### Scenario: Identical run specs reuse the same run directory
- **GIVEN** two `PipelineRunSpec` payloads are semantically identical
- **WHEN** they are normalized and hashed
- **THEN** they produce the same `params_hash`
- **AND** artifacts are written under the same `artifacts/runs/<params_hash>/` directory

#### Scenario: Stable list ordering avoids accidental hash drift
- **GIVEN** `PipelineRunSpec` includes list fields like `timeframes` and `pairs`
- **WHEN** operators author batch specs
- **THEN** they keep list ordering stable so the computed `params_hash` does not change due to reordering alone

### Requirement: Avoid concurrent writes to Iceberg
Operators SHOULD avoid launching multiple runs that write to the same Iceberg tables concurrently.

#### Scenario: Concurrent runs attempt to write to the same table
- **GIVEN** multiple Prefect flow runs are executing at the same time
- **WHEN** they attempt to append/overwrite the same Iceberg table concurrently
- **THEN** one or more runs may fail due to optimistic concurrency conflicts
- **AND** operators SHOULD serialize writes (worker `--limit 1`, data_concurrency=1) for reliability
