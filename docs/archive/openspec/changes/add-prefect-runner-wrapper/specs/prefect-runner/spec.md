# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: Prefect integration is uv-native and optional
The system SHALL support running pipelines under Prefect using only `uv` commands, without requiring global Python
or `pip`.

#### Scenario: Install and run Prefect wrapper with uv only
- **GIVEN** a clean checkout of the repo
- **WHEN** the user installs Prefect support via `uv sync --extra prefect`
- **AND** executes the wrapper via `uv run --extra prefect python workflows/prefect/run_flow.py --spec run_spec.json`
- **THEN** the run executes without `pip` or global Python usage

#### Scenario: Run Prefect directly from CLI (seamless mode)
- **GIVEN** Prefect support is installed via `uv sync --extra prefect`
- **WHEN** the user runs `uv run --extra prefect tvscreener-scan --runner prefect ...`
- **THEN** the system executes the run via Prefect without requiring an intermediate exported spec file
- **AND** writes artifacts under `artifacts/runs/<params_hash>/` by default (or the CLI-provided `--artifacts-dir`)

Extensions-owned pipelines note:
- When upstream `tvscreener` from the package index does not ship `tvscreener-scan`, the equivalent CLI is
  `uv run --project extensions --extra prefect tvscreener-ext-scan --runner prefect ...`.

#### Scenario: Extensions runner executes Iceberg + DuckDB pipelines
- **GIVEN** upstream `tvscreener` provides TradingView API screeners (`tvscreener.core.*`)
- **WHEN** an operator runs `tvscreener-ext-scan --runner prefect --pipeline both ...`
- **THEN** the data stage writes Iceberg tables
- **AND** the analytics stage reads from Iceberg and writes results parquet + matrix artifacts

Legacy compatibility: `--artifacts-dir artifacts/prefect` continues to work during migration.

#### Scenario: Prefect is the default workflow runner for scanner commands
- **GIVEN** the repository is configured for workflow-managed execution
- **WHEN** an operator runs `tvscreener-scan` without explicitly passing `--runner`
- **THEN** scanner execution defaults to `prefect`
- **AND** operators can explicitly override to `--runner local` for debugging/fallback

#### Scenario: Environment defaults simplify Prefect startup for CLI runs
- **GIVEN** operators use the provided `.env` template defaults
- **WHEN** they run scanner commands with implicit Prefect runner
- **THEN** the CLI loads `.env` into the environment for Prefect settings
- **AND** Prefect state is isolated (`PREFECT_HOME=.prefect-home`)
- **AND** runs can target a dedicated server via `PREFECT_API_URL=http://127.0.0.1:4200/api`
- **AND** startup timeout default is sufficient for first-run migrations (`PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180`)

#### Scenario: `.env` is local-only and gitignored
- **GIVEN** the repo provides `.env.example`
- **WHEN** an operator runs `cp .env.example .env` and customizes values
- **THEN** the workflow defaults apply locally
- **AND** `.env` is not committed to git

#### Scenario: Dedicated Prefect server is supported for parity
- **GIVEN** operators want local development to match production orchestration behavior
- **WHEN** they start a Prefect server with `prefect server start --background`
- **AND** set `PREFECT_API_URL=http://127.0.0.1:4200/api`
- **THEN** runs execute against that server (no ephemeral server startup)

#### Scenario: Wrapper scripts resolve artifacts under repo root
- **GIVEN** the user executes `python workflows/prefect/run_flow.py` or `python workflows/prefect/run_batch.py`
- **WHEN** the user supplies a relative `--artifacts-dir` (or uses the default `artifacts/runs`)
- **THEN** the wrapper resolves that directory relative to the **repo root** so reruns are stable from any cwd

#### Scenario: Prefect runtime is uv-managed and stable to start
- **GIVEN** the operator is using `uv` with an **uv-managed Python** for this repo
- **WHEN** the Prefect wrapper starts its temporary API server for local orchestration
- **THEN** the run can be made reliable by:
  - pinning a compatible Python version (project baseline: `3.12`)
  - setting `PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS` high enough for first-run migrations (e.g. `180`)
  - optionally isolating Prefect state using `PREFECT_HOME=$PWD/.prefect-home`

#### Scenario: Prefect local DB can be reset on migration mismatch
- **GIVEN** the temporary Prefect server fails to start due to a migration resolution error
  (e.g. `Can't locate revision identified by ...`)
- **WHEN** the operator resets Prefect state by moving/removing the existing `PREFECT_HOME` directory
  (e.g. renaming `.prefect-home` and creating a fresh one)
- **THEN** a subsequent run starts successfully and applies migrations from a clean database

#### Scenario: Base library remains engine-free
- **WHEN** the user installs/runs the base library without the Prefect extra
- **THEN** the system does not require Prefect dependencies
- **AND** core import paths do not import Prefect

### Requirement: Prefect runs can persist and emit matrix output
When executing under Prefect, the system SHALL persist the matrix output as an artifact when `matrix` rendering is requested.

#### Scenario: Prefect analytics writes results parquet
- **WHEN** a run executes with `--runner prefect` and an effective analytics stage
- **THEN** the wrapper writes an analytics results parquet under `artifacts/runs/<params_hash>/`

#### Scenario: Prefect persists matrix output as an artifact
- **GIVEN** a run is requested with `matrix=true`
- **WHEN** the Prefect runner executes the run
- **THEN** it writes `matrix.txt` under `artifacts/runs/<params_hash>/`
- **AND** the text includes the snapshot label when available

#### Scenario: Operator can still force local interactive output
- **GIVEN** an operator wants the Rich-rendered matrix table in their local terminal
- **WHEN** they execute the same run with `--runner local --matrix`
- **THEN** the matrix is rendered to stdout using Iceberg-backed analytics inputs

### Requirement: Prefect wrapper executes data and analytics pipelines as distinct tasks
The Prefect wrapper SHALL execute pipeline modes in a way that preserves the architecture boundary between data and
analytics.

Terminology:
- `pipeline_mode=data`: ingestion + feature engineering + Iceberg writes
- `pipeline_mode=analytics`: reporting + Iceberg reads + artifact writes

#### Scenario: Data pipeline task is allowed to write Iceberg
- **WHEN** the wrapper executes a run with `pipeline_mode == "data"`
- **THEN** it executes the data pipeline only (fetch → Iceberg writes)

#### Scenario: Analytics pipeline task is read-only
- **WHEN** the wrapper executes a run with `pipeline_mode == "analytics"`
- **THEN** it executes the analytics pipeline only (Iceberg reads → render/export)
- **AND** it does not mutate Iceberg tables unless explicitly modeled as an analytics product

#### Scenario: Both mode composes data then analytics
- **WHEN** the wrapper executes a run with `pipeline_mode == "both"`
- **THEN** it runs the data task first
- **AND** runs the analytics task second using the canonical lakehouse outputs

#### Scenario: Prefect tasks have bounded runtime
- **GIVEN** upstream API calls or Iceberg writes can hang
- **WHEN** a run executes under Prefect
- **THEN** the Prefect task has a finite timeout
- **AND** operators can configure the timeout via `TVSCREENER_PREFECT_TASK_TIMEOUT_SECONDS`
- **AND** if the task runs in a worker thread, the timeout MAY only be enforced after blocking calls return

#### Scenario: Scheduled batch runs do not crash on flow run naming
- **GIVEN** `tvscreener-batch` is deployed for worker execution
- **WHEN** the deployment creates a scheduled flow run
- **THEN** the flow run starts successfully under a worker
- **AND** the flow run name template references only declared flow parameters

#### Scenario: Prefect publishes matrix and results artifacts
- **GIVEN** a run completes with `matrix.md` and a results parquet
- **WHEN** `TVSCREENER_PUBLISH_RESULTS_SUMMARY=1`
- **THEN** Prefect publishes a markdown artifact for the matrix
- **AND** Prefect publishes a table artifact preview of results by default
- **AND** when `TVSCREENER_PUBLISH_TABLE_ARTIFACTS=0`, Prefect does not publish the table artifact

#### Scenario: Table artifacts come from DuckDB semantic tables
- **GIVEN** an analytics run writes DuckDB semantic tables under the run directory
- **WHEN** Prefect publishes table artifacts
- **THEN** it reads `results_top_rows.json` and publishes `tvscreener-results-*`
- **AND** it reads `results_grade_summary.json` and publishes `tvscreener-results-*-summary`

#### Scenario: Both mode writes Iceberg then renders via analytics engine
- **GIVEN** the lakehouse catalog is configured (local or remote)
- **WHEN** a `pipeline_mode == "both"` run executes under Prefect
- **THEN** the data task writes the canonical tables in order (Bronze -> Silver -> Gold -> signals)
- **AND** the analytics task reads from Iceberg snapshots (no upstream fetch)
- **AND** the run writes `run_spec.json`, `run_result.json`, `matrix.txt` (when requested), and a results parquet

#### Scenario: Full refresh avoids redundant upstream fetch for strategy
- **GIVEN** strategy analytics consumes `tvscreener.signals_latest`
- **WHEN** the operator runs a full refresh for a large universe (e.g. forex `universe=all`)
- **THEN** the batch SHOULD run:
  - opportunity as `pipeline_mode=both` (fetch + persist + matrix artifacts)
  - strategy as `pipeline_mode=analytics` (matrix artifacts only)
- **AND** it SHOULD NOT run a separate strategy `pipeline_mode=data` that duplicates upstream fetch

### Requirement: Prefect wrapper uses `params_hash` for idempotent identification
The wrapper SHOULD use `PipelineRunSpec.params_hash` to identify runs in the orchestration layer.

#### Scenario: Flow run is tagged or named by params hash
- **WHEN** the wrapper creates a Prefect flow run
- **THEN** it uses `params_hash` in the flow run name and/or tags

#### Scenario: Batch rerun can skip completed stages
- **GIVEN** a previous batch run wrote artifacts under `artifacts/runs/<params_hash>/`
- **WHEN** the user reruns the same batch with `--skip-existing`
- **THEN** the wrapper skips runs where `run_result.json` already exists
- **AND** it returns a batch result payload that includes `skipped` flags per run

### Requirement: Prefect wrapper writes deterministic artifacts by default
The wrapper SHALL produce deterministic on-disk artifacts keyed by `params_hash` so results can be consumed without
interactive console rendering.

#### Scenario: Wrapper writes spec and run results
- **WHEN** the wrapper executes any run
- **THEN** it writes `run_spec.json` under `artifacts/runs/<params_hash>/`
- **AND** it writes `run_result.json` under `artifacts/runs/<params_hash>/`

#### Scenario: Analytics produces a default results file when output is not provided
- **WHEN** the wrapper executes a run whose effective pipeline includes analytics (`analytics` or `both`)
- **AND** `PipelineRunSpec.output` is not provided
- **THEN** it writes a default results file under `artifacts/runs/<params_hash>/` (e.g., `<scanner_family>_results.parquet`)

### Requirement: Default-runner transition is safety-gated
Switching CLI default runner to Prefect SHALL be gated by readiness checks.

#### Scenario: Default switch requires readiness audit pass
- **WHEN** maintainers enable Prefect as default runner
- **THEN** readiness checks confirm:
  - analytics-only runs remain read-only for Iceberg product tables
  - artifact contract audits are complete (paths, determinism, discoverability)
  - multi-asset/multi-timeframe FR regression suite passes

### Requirement: Analytics artifacts are self-describing for machine consumers
When analytics runs under Prefect, the resulting artifacts SHALL be discoverable without reading logs.

#### Scenario: Analytics result JSON includes results path
- **WHEN** the wrapper executes `pipeline_mode == "analytics"`
- **THEN** the returned payload includes a `results_path`
- **AND** `run_result.json` includes the same `results_path`

#### Scenario: Both mode embeds analytics results path
- **WHEN** the wrapper executes `pipeline_mode == "both"`
- **THEN** `run_result.json` includes `analytics.results_path`
- **AND** the file referenced by `analytics.results_path` exists when the analytics task succeeds

#### Scenario: DuckDB-powered analytics is reproducible when installed
- **GIVEN** the optional analytics/semantic dependencies are installed
- **WHEN** analytics runs under Prefect
- **THEN** any DuckDB-powered summaries (semantic layer, audits/reports) can be computed from Iceberg-backed inputs
- **AND** the outputs do not depend on interactive CLI output
