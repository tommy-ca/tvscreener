## Design: Prefect-first runner wrapper (uv-only)

### Principle
Prefect integration is implemented as a **thin wrapper** around the existing runner abstraction:
- `PipelineRunSpec` is the single input payload (JSON)
- `RunResult` is the single output payload (JSON)
- Prefect tasks call a local runner (`LocalRunner.run(spec)`) to execute pipelines in-process

### Constraints
- **uv-only**: No `pip`, no `uv pip`, no reliance on global Python.
- **Dependency isolation**: Prefect is enabled via an optional dependency extra; core `tvscreener` codepaths do not
  require Prefect imports.
- **Runtime compatibility**: Prefect runs under an **uv-managed Python** pinned by the repo (baseline: `3.12`).
  - For local temporary-server runs, first-time startup may require a higher
    `PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS` to complete migrations.
  - For predictable state (avoid mixing old Prefect DBs), prefer `PREFECT_HOME=$PWD/.prefect-home`.

### Packaging approach
Prefer a single repo workspace managed by `uv`:
- Add `prefect` under `pyproject.toml` optional dependencies:
  - `prefect = ["prefect>=3"]`
- Install on demand:
  - `uv sync --extra prefect`

This keeps the default install lean while making Prefect available when needed.

### Wrapper location
Place Prefect-specific code under:
- `workflows/prefect/`

The wrapper directory is intentionally not part of the `tvscreener` import package so engine dependencies remain
optional and avoid polluting core APIs.

### Execution model

#### Inputs
- `PipelineRunSpec` JSON file (produced via `--runner export` or created externally)

#### Tasks
- `run_data(spec)`:
  - executes `pipeline_mode=data` (or the data component of `both`)
  - allowed to write Iceberg
- `run_analytics(spec)`:
  - executes `pipeline_mode=analytics` (or the analytics component of `both`)
  - MUST be read-only w.r.t. Iceberg tables

#### Flow composition
- If `pipeline_mode == "data"`: run `run_data` only
- If `pipeline_mode == "analytics"`: run `run_analytics` only
- If `pipeline_mode == "both"`: run `run_data` then `run_analytics`

### Batch execution (scale baseline)
For scale, Prefect SHOULD execute runs via a batch driver that:
- expands a higher-level batch definition into a list of `PipelineRunSpec` objects (matrix expansion)
- optionally shards large universes into explicit `pairs` chunks (`max_pairs_per_run`)
- fans out data and analytics tasks with bounded concurrency
- writes artifacts for each run under `artifacts/prefect/<params_hash>/` and a batch summary under
  `artifacts/prefect/batch/<batch_id>/`

### Artifact conventions (v1)
The wrapper writes deterministic artifacts keyed by `params_hash`:
- Always:
  - `run_spec.json`
- Result JSON:
  - `run_result_data.json` for `pipeline_mode == "data"`
  - `run_result_analytics.json` for `pipeline_mode == "analytics"`
  - `run_result.json` for `pipeline_mode == "both"` (includes `data` + `analytics` sub-results)
- Analytics output:
  - default `<scanner_family>_results.parquet` under the run directory when `PipelineRunSpec.output` is not set

### Artifacts audit checklist (analytics workflows)
When reviewing Prefect analytics artifacts (`pipeline_mode=analytics` and analytics stage of `both`), verify:
- **Path semantics**
  - relative `artifacts_dir` resolution is consistent with the entrypoint:
    - seamless CLI runner (`tvscreener-scan --runner prefect`) uses the current process working directory
    - repo-local wrapper scripts (`workflows/prefect/run_flow.py`, `workflows/prefect/run_batch.py`) set cwd to repo root
      so relative `--artifacts-dir` is stable across reruns
- **Discoverability**
  - result JSON includes `artifacts_dir`
  - when analytics runs, result JSON includes `results_path` that points to the emitted parquet file
- **Determinism**
  - artifact directory is `artifacts/prefect/<params_hash>/` (or configured base dir)
  - filenames do not include timestamps
  - analytics default file name is `<scanner_family>_results.parquet`
- **Contract completeness**
  - machine consumer can locate: run spec, run result, analytics output with only the JSON artifacts (no logs)

### CI validation approach (no upstream network calls)
To validate the Prefect wrapper wiring in CI without calling TradingView:
- install `--extra prefect` + `--extra cli`
- run a smoke test that executes the Prefect flow with a stubbed `LocalRunner.run(...)`
- assert artifact paths and filenames are correct and deterministic

### Verification / rerun guidance
When validating upstream API semantics (e.g., TradingView scan batching), prefer running both:
- **direct CLI runs** (`--pipeline data|analytics`) to validate core behavior
- **Prefect runs** (`run_flow.py` / `run_batch.py`) to validate workflow execution + artifact writing

#### Idempotency and naming
- Use `spec.params_hash` as:
  - the Prefect flow run name (or a tag)
  - an idempotency key for external systems
  - a potential cache key (future; optional)

### uv-native commands (examples)

#### 1) Install Prefect (optional)
```bash
uv sync --extra prefect
```

#### 2) Export a run spec (engine-agnostic)
```bash
uv run tvscreener-scan --runner export --scanner opportunity --pipeline both --asset-type forex --universe majors > run_spec.json
```

#### 3) Execute with Prefect locally
```bash
uv run --extra prefect python workflows/prefect/run_flow.py --spec run_spec.json
```

### Known issues / improvement suggestions
1) **Per-process rate limiting only**
   - Current throttling protects a single worker process; it is not a distributed/global limiter.
   - For true scale, add a shared limiter (Redis/db) or route all fetch through a single throttled service.

2) **Batch orchestration currently phases all data then all analytics**
   - This is safe, but increases latency. Consider per-run chaining:
     - as soon as one shard’s data task finishes, trigger its analytics task.
   - This also enables better partial progress when large batches take time.

3) **Idempotent skip**
   - Implemented for batch runs via `workflows/prefect/run_batch.py --skip-existing`.
   - Follow-up: consider adding similar semantics to the seamless CLI Prefect runner mode.

4) **Artifact schema**
   - Standardize artifact filenames across scanners (`*_results.parquet`, `run_result.json`, `run_spec.json`)
   - Optionally add a small `metrics.json` (API calls, coverage, retries) for observability.

5) **Prefect server overhead**
   - Local temporary server per invocation is convenient but adds overhead.
   - Optionally support running against an existing Prefect server/worker setup for long batches.
   - Operational tip: set `PREFECT_HOME=$PWD/.prefect-home` and consider
     `PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180` for first-run migrations.

### Backward compatibility
- CLI default behavior now uses `--runner prefect` (readiness gates passed).
- `--runner local` remains supported as explicit fallback for debugging and incident mitigation.

## Default-runner transition plan

### Readiness gates (must pass before flipping default)
1. Analytics read-only audit completed (`pipeline_mode=analytics` does not mutate product tables)
2. Artifact audit completed (`9.1`..`9.5` tasks)
3. FR regression suite green (multi-asset identity, deterministic fan-out, product-table contracts)
4. Rerun reliability proven on representative universes (majors/minors and all-universe shards)

### Rollout steps
1. Complete remaining verification/audit tasks in this change package
2. Flip CLI default runner from `local` to `prefect`
3. Run post-flip smoke (`data`, `analytics`, `both`) with explicit fallback test (`--runner local`)
4. Keep local fallback documented in runbook for operational recovery

### Default configuration baseline (post-flip)
- `.env` template includes Prefect runtime defaults:
  - `PREFECT_HOME=.prefect-home`
  - `PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180`
- scanner settings defaults align for predictable quick runs:
  - default universe: `majors`
  - default timeframes: `240,60,15`
