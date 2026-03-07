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
- **AND** writes artifacts under `artifacts/prefect/<params_hash>/` (or the CLI-provided `--artifacts-dir`)

#### Scenario: Prefect is the default workflow runner for scanner commands
- **GIVEN** the repository is configured for workflow-managed execution
- **WHEN** an operator runs `tvscreener-scan` without explicitly passing `--runner`
- **THEN** scanner execution defaults to `prefect`
- **AND** operators can explicitly override to `--runner local` for debugging/fallback

#### Scenario: Environment defaults simplify Prefect startup for CLI runs
- **GIVEN** operators use the provided `.env` template defaults
- **WHEN** they run scanner commands with implicit Prefect runner
- **THEN** Prefect state is isolated (`PREFECT_HOME=.prefect-home`)
- **AND** startup timeout default is sufficient for first-run migrations (`PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180`)

#### Scenario: Wrapper scripts resolve artifacts under repo root
- **GIVEN** the user executes `python workflows/prefect/run_flow.py` or `python workflows/prefect/run_batch.py`
- **WHEN** the user supplies a relative `--artifacts-dir` (or uses the default `artifacts/prefect`)
- **THEN** the wrapper resolves that directory relative to the **repo root** so reruns are stable from any cwd

#### Scenario: Prefect runtime is uv-managed and stable to start
- **GIVEN** the operator is using `uv` with an **uv-managed Python** for this repo
- **WHEN** the Prefect wrapper starts its temporary API server for local orchestration
- **THEN** the run can be made reliable by:
  - pinning a compatible Python version (project baseline: `3.12`)
  - setting `PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS` high enough for first-run migrations (e.g. `180`)
  - optionally isolating Prefect state using `PREFECT_HOME=$PWD/.prefect-home`

#### Scenario: Base library remains engine-free
- **WHEN** the user installs/runs the base library without the Prefect extra
- **THEN** the system does not require Prefect dependencies
- **AND** core import paths do not import Prefect

### Requirement: Prefect wrapper executes data and analytics pipelines as distinct tasks
The Prefect wrapper SHALL execute pipeline modes in a way that preserves the architecture boundary between data and
analytics.

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
- **GIVEN** a previous batch run wrote artifacts under `artifacts/prefect/<params_hash>/`
- **WHEN** the user reruns the same batch with `--skip-existing`
- **THEN** the wrapper skips stages where `run_result_data.json` and/or `run_result_analytics.json` already exist
- **AND** it returns a batch result payload that includes `skipped` flags per run

### Requirement: Prefect wrapper writes deterministic artifacts by default
The wrapper SHALL produce deterministic on-disk artifacts keyed by `params_hash` so results can be consumed without
interactive console rendering.

#### Scenario: Wrapper writes spec and run results
- **WHEN** the wrapper executes any run
- **THEN** it writes `run_spec.json` under `artifacts/prefect/<params_hash>/`
- **AND** it writes a result JSON:
  - `run_result_data.json` for `pipeline_mode == "data"`
  - `run_result_analytics.json` for `pipeline_mode == "analytics"`
  - `run_result.json` for `pipeline_mode == "both"` (includes `data` + `analytics` sub-results)

#### Scenario: Analytics produces a default results file when output is not provided
- **WHEN** the wrapper executes a run whose effective pipeline includes analytics (`analytics` or `both`)
- **AND** `PipelineRunSpec.output` is not provided
- **THEN** it writes a default results file under `artifacts/prefect/<params_hash>/` (e.g., `<scanner_family>_results.parquet`)

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
- **AND** `run_result_analytics.json` includes the same `results_path`

#### Scenario: Both mode embeds analytics results path
- **WHEN** the wrapper executes `pipeline_mode == "both"`
- **THEN** `run_result.json` includes `analytics.results_path`
- **AND** the file referenced by `analytics.results_path` exists when the analytics task succeeds
