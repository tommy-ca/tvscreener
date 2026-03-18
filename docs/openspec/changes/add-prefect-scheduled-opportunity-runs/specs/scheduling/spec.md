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

### Requirement: Analytics rerenders can be deployed
The system SHOULD support creating Prefect deployments that rerender analytics matrices on a schedule.

#### Scenario: Operator registers analytics-only deployments
- **GIVEN** batch specs exist for `pipeline_mode=analytics`
- **WHEN** deployments are registered for those batch specs
- **THEN** Prefect can execute periodic analytics rerenders without upstream fetches

#### Scenario: Scheduled matrix rerenders are not sharded
- **GIVEN** an operator wants a complete matrix view per universe
- **WHEN** they register analytics-only deployments
- **THEN** the batch specs avoid pair sharding so a single run generates a complete matrix

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

### Requirement: Matrix views are visible in the Prefect UI
When running under Prefect, matrix views SHOULD be published as Prefect Markdown artifacts for quick inspection.

#### Scenario: Prefect run publishes a Markdown artifact
- **GIVEN** a Prefect flow run executed with `--matrix`
- **WHEN** matrix output is generated
- **THEN** a Prefect Markdown artifact is created containing the matrix (in a fenced code block)

#### Scenario: One artifact per run spec
- **GIVEN** operators want minimal Prefect artifact noise
- **WHEN** analytics runs under Prefect
- **THEN** exactly one per-run-spec artifact is published by default (Markdown)
- **AND** it includes the matrix plus a small decision preview (top rows)

### Requirement: Table reports can be published from Iceberg queries
Operators SHOULD be able to publish small tabular reports (derived from DuckDB queries over Iceberg tables) into the Prefect UI.

#### Scenario: Operator publishes a data freshness table
- **GIVEN** an operator can query Iceberg tables via DuckDB
- **WHEN** they create a Prefect Table artifact from the query result
- **THEN** the Prefect UI shows the data freshness table alongside the flow run

#### Scenario: Batch deployments publish a table summary
- **GIVEN** a Prefect batch deployment runs multiple specs
- **WHEN** the batch completes
- **THEN** the flow publishes a Prefect Table artifact summarizing per-run results

### Requirement: Analytics results tables are visible in the Prefect UI
When running under Prefect, analytics result rows SHOULD be published as a Prefect Table artifact.

#### Scenario: Prefect analytics run publishes a results table
- **GIVEN** a Prefect flow run executed `pipeline_mode=analytics`
- **WHEN** analytics writes a results parquet artifact
- **THEN** a Prefect Table artifact is created from the top result rows
- **AND** the table includes decision features when present (e.g. `PAIR`, `Price`, `RVOL`, `Volume`, `ENSEMBLE_SCORE`, `GRADE`, `DIRECTION`, `GRID_ALIGNED`, `GRID_TOTAL`, `CONFLUENCE_LEVEL`, `TOTAL_CONFLUENCE`, `TF_CONFLUENCE`, and factor scores/dirs)

#### Scenario: Results tables are derived from Iceberg semantic surface
- **GIVEN** the run wrote signals into `tvscreener.signals_batch`
- **WHEN** the Prefect results table artifact is created
- **THEN** it is derived from a query over `tvscreener.signals_batch` filtered by the `data` params hash
- **AND** it falls back to per-run parquet outputs only if the Iceberg query fails

#### Scenario: Analytics run publishes a grade summary
- **GIVEN** a Prefect flow run executed `pipeline_mode=analytics`
- **WHEN** matrix-relevant attributes exist (e.g. `GRADE`, `DIRECTION`)
- **THEN** the flow publishes a second Table artifact summarizing counts/averages by grade and direction

#### Scenario: Summary table publication is optional
- **GIVEN** operators want fewer Prefect artifacts per run
- **WHEN** `TVSCREENER_PUBLISH_RESULTS_SUMMARY` is not set to `1`
- **THEN** only the main `tvscreener-results-...` table is published

#### Scenario: Table artifacts are opt-in
- **GIVEN** one artifact per run spec is the default
- **WHEN** `TVSCREENER_PUBLISH_TABLE_ARTIFACTS` is not set to `1`
- **THEN** no per-run Table artifacts are published

### Requirement: `ROC_SCORE` is derived from canonical ROC columns
The system SHOULD compute `ROC_SCORE` from canonical ROC columns (e.g. `ROC_15`, `ROC_60`, `ROC_240`) when present.

#### Scenario: Canonical ROC columns produce non-zero `ROC_SCORE`
- **GIVEN** an opportunity row has non-zero `ROC_15/ROC_60/ROC_240`
- **WHEN** scoring runs
- **THEN** `ROC_SCORE` is non-zero (mean of the available ROC columns)

### Requirement: A semantic layer can define shared dimensions and measures
The system SHOULD support defining a semantic model (dimensions + measures/metrics) so that Prefect artifacts and DuckDB/Iceberg queries share consistent definitions.

#### Scenario: Operator defines decision metrics once
- **GIVEN** a semantic model exists for analytics outputs
- **WHEN** an operator publishes a Prefect Table artifact
- **THEN** the table can be derived from semantic dimensions/measures rather than ad-hoc column selection

#### Scenario: Semantic model includes the matrix view surface
- **GIVEN** the opportunity matrix view is rendered from `tvscreener.signals_latest`
- **WHEN** a semantic model is defined
- **THEN** it includes matrix-level dimensions (pair, timeframe_set_id, direction, grade)
- **AND** it includes matrix-level measures (opportunity_count, counts by grade/direction, average scores)

#### Scenario: Semantic model is validated and versioned
- **GIVEN** a semantic model is stored in the repo
- **WHEN** CI runs
- **THEN** semantic model validation runs (schema + query compilation)
- **AND** changes to the model are code-reviewed like any other change

#### Scenario: Sidemantic integration is gated by licensing
- **GIVEN** Sidemantic is AGPL-3.0
- **WHEN** the project evaluates adopting it
- **THEN** the decision is recorded and approved before adding Sidemantic as a required dependency

#### Scenario: Sidemantic is used only when enabled
- **GIVEN** Sidemantic is installed as an optional extra
- **WHEN** `TVSCREENER_SEMANTIC_RUNTIME=sidemantic`
- **THEN** analytics table artifacts are generated from Sidemantic semantic queries
- **AND** when not enabled, they are generated via the built-in DuckDB/Iceberg SQL

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
- **AND** they use a consistent `timeframes` order (recommended: `15,60,240`) across runs

### Requirement: Avoid concurrent writes to Iceberg
Operators SHOULD avoid launching multiple runs that write to the same Iceberg tables concurrently.

#### Scenario: Concurrent runs attempt to write to the same table
- **GIVEN** multiple Prefect flow runs are executing at the same time
- **WHEN** they attempt to append/overwrite the same Iceberg table concurrently
- **THEN** one or more runs may fail due to optimistic concurrency conflicts
- **AND** operators SHOULD serialize writes (worker `--limit 1`, data_concurrency=1) for reliability
