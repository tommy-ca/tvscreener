# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Pipeline runner abstraction

### Principle
The library defines **deterministic pipelines** and produces/consumes **Iceberg tables**.
Execution concerns (parallelism, retries, scheduling, scaling) live in a **runner layer**.

### Non-goals (scope guard)
- Introduce a hard dependency on workflow engines (Dagster/Prefect/Temporal/etc.) in the core `tvscreener` package.
- Fully refactor the in-process orchestrator into step-level primitives (tracked as a follow-up decomposition).

### Components

#### 1) `PipelineRunSpec` (serializable contract)
`PipelineRunSpec` is the canonical payload exchanged between:
- CLI / API clients
- workflow engines (external schedulers)
- local runner

It MUST be JSON-serializable and stable-hashable (`params_hash`) to support:
- idempotent submissions
- caching / de-dupe
- audit reproducibility

Minimum fields:
- `scanner_family`: `opportunity | strategy`
- `pipeline_mode`: `data | analytics | both`
- `asset_type`
- `universe` (or explicit `pairs`)
- `pairs` (optional explicit list)
- `timeframes` (list)
- `timeframe_set_id` (derived)
- `config_path` (optional)
- `sql` / `sql_params` / `filters` (analytics filters)
- `created_at_utc` (client-side)
- `params_hash`
- `code_version` (optional, injected by runner)
- `spec_version` (recommended; allows forward-compatible evolution of the exported JSON shape)

#### 2) `PipelineRunner` interface
The runner executes the spec.

Local:
- `run(spec) -> RunResult` (blocking)

External (future / optional):
- Runners MAY add non-blocking submission and status APIs, but the baseline contract is synchronous `run(spec)`.

This interface is intentionally minimal so adapters can wrap:
- Prefect flows
- Dagster jobs
- Temporal workflows
- Airflow DAGs
- Argo workflows

#### 3) `RunResult` contract
The result is structured and machine-readable:
- `params_hash`
- `scanner_family`
- `pipeline_mode_executed`
- `started_at_utc`, `finished_at_utc`
- `success`, `exit_code`
- `result_count` (best-effort count from the orchestrator)
- `errors` (if any)
- optional audit fields: `tables_read`, `tables_written` (best-effort; may be empty)

Future extensions (not required for v1) may include:
- `run_id` / run envelope identifiers
- per-stage counts and timing
- `max_fetched_at_utc` for product tables (e.g., `signals_latest`)

### Lightweight workflow-engine integration model
The integration goal is “**bring your own engine**” with a tiny adapter surface:

#### A) Export runner (engine-agnostic)
- CLI builds a `PipelineRunSpec`
- `--runner export` emits the spec JSON (stdout or file)
- external engine submits that JSON as the “run config / parameters” payload

This keeps the core library free of orchestration dependencies and makes engines optional tooling.

#### B) Wrapper scripts (outside the core library package)
Provide a minimal “engine wrapper” script that:
- reads `PipelineRunSpec` JSON
- validates it (same Pydantic model)
- calls `LocalRunner.run(spec)` inside a task/activity/step

Wrappers SHOULD:
- use `params_hash` as an idempotency key / cache key / run name
- surface `RunResult` as the engine’s artifact / output payload

Wrappers MUST NOT:
- require changes to `tvscreener` core to support one specific engine

Prefect-first reference:
- This repo tracks a Prefect wrapper plan as `docs/openspec/changes/add-prefect-runner-wrapper/`.

#### C) Optional HTTP submit runner (thin integration)
A future `HttpRunner` can POST a spec to an operator-controlled endpoint.
The endpoint is responsible for submission to an engine of choice.

### Atomic steps (recommended decomposition for engines)
Workflow engines operate best when units of work are small, retryable, and have explicit inputs/outputs.
This change does not require the refactor, but the runner model should be compatible with it.

Recommended step taxonomy:

#### Data pipeline (writes Iceberg)
- ResolveInputs: expand universe → pairs, parse timeframes, compute `timeframe_set_id`
- InitRunEnvelope: produce `run_id`, attach reproducibility fields (`params_hash`, `code_version`)
- FetchUpstream: call TradingView, produce raw dataframe
- PersistBronze: write raw snapshot to Bronze
- NormalizeSilver: standardize schema + identifiers
- PersistSilver: write normalized snapshot to Silver
- ScoreGold: compute scores/risk/features
- PersistGold: write Gold snapshot
- PersistSignalsLatest: materialize “latest-per-entity” product table

#### Analytics pipeline (read-only)
- LoadSignalsLatest: query Iceberg product table
- ApplyEdgeFilters: apply SQL + filter expressions
- ComputeStrategySignals: strategy-only compute from loaded data
- RenderMatrix: render the CLI matrix view (or return structured payload)
- ExportArtifacts: optional debug exports (non-canonical)

Compatibility rules:
- Only `Persist*` steps may mutate Iceberg tables.
- Analytics-only MUST remain read-only unless explicitly modeled as a product table.

### Execution semantics

#### Data pipeline
- Input: `PipelineRunSpec` with `pipeline_mode in {data,both}`
- Output: Iceberg writes to medallion tables + product table(s)
- Runner responsibilities:
  - retries around upstream fetch
  - record failure modes and partial coverage (future)

#### Analytics pipeline
- Input: `PipelineRunSpec` with `pipeline_mode in {analytics,both}`
- Output: rendered matrix view + optional exported file
- MUST NOT write Iceberg tables (read-only), unless explicitly modeled as an analytics product.

### Backward compatibility
- CLI defaults: `--runner prefect`, `--pipeline both`
- `--runner local` remains supported as an explicit fallback for debugging/offline runs.
- Existing API surfaces remain; the runner abstraction is additive.

### Future workflow engines

The `PipelineRunSpec` abstraction is intentionally workflow-engine-agnostic. Alternative engines can be evaluated and integrated as additional runners without changing the scan core.

See `docs/openspec/changes/evaluate-workflow-engine-options/design.md`.
