## Tasks

## 1. Specs and documentation (this change)
- [x] 1.1 Define Prefect wrapper requirements (uv-only, optional deps, data vs analytics tasks)
- [x] 1.2 Document wrapper design + uv-native commands
- [x] 1.3 Cross-link from runner abstraction change (`add-pipeline-runner-abstraction`) to this Prefect wrapper
- [x] 1.4 Document local Prefect runtime constraints (uv-managed Python pin + ephemeral server startup timeout)

## 2. Dependencies (uv-managed)
- [x] 2.1 Add `prefect` optional dependency extra to root `pyproject.toml`
- [x] 2.2 Ensure `uv.lock` updates correctly (no global Python / pip usage)

## 3. Runner prerequisites (depends on `add-pipeline-runner-abstraction`)
- [x] 3.1 Implement `PipelineRunSpec` + `RunResult`
- [x] 3.2 Implement `LocalRunner.run(spec)`
- [x] 3.3 Add CLI `--runner {local,export}` and implement `--runner export` (stdout JSON)

## 4. Prefect wrapper implementation
- [x] 4.1 Add `workflows/prefect/run_flow.py`:
  - reads a `PipelineRunSpec` JSON file
  - uses Prefect tasks for `data` and `analytics` execution
  - prints/writes `RunResult` JSON
- [x] 4.2 Use `spec.params_hash` in flow/task run naming or tags
- [x] 4.3 Add a short runbook `workflows/prefect/README.md` with uv-only commands
- [x] 4.4 Add forex majors/minors batch templates under `workflows/prefect/batches/`

## 5. Verification
- [x] 5.1 Local run: `uv sync --extra prefect` then execute `both` (opportunity majors) via Prefect wrapper
- [x] 5.2 Local run: execute `analytics` only and confirm Iceberg product tables are unchanged
- [x] 5.3 Local run: execute `data` only and confirm Iceberg tables were updated
- [x] 5.4 CI: add Prefect wrapper smoke test + workflow job (stub LocalRunner; verify deterministic artifacts)

## 9. Artifacts audit (Prefect analytics workflows)
- [x] 9.1 Inventory artifacts for `pipeline_mode=analytics` and analytics stage of `both` (single-run + batch)
- [x] 9.2 Audit path semantics: cwd vs repo-root resolution for relative `--artifacts-dir`
- [x] 9.3 Audit contract completeness for machine consumption:
  - result JSON always includes `artifacts_dir` and `results_path` when analytics runs
  - artifact filenames are consistent across scanners
- [x] 9.4 Audit determinism/idempotency expectations for analytics output files (overwrite vs append)
- [x] 9.5 Capture follow-ups as tasks (or a new OpenSpec change if contract changes are needed)

## 10. Prefect default-runner transition
- [x] 10.1 Readiness audit for default switch:
  - [x] confirm `5.2` analytics-only read-only audit
  - [x] confirm `9.1`..`9.5` artifact audits complete
  - [x] confirm FR regression suite passes after Prefect reruns
- [x] 10.2 Flip CLI default runner to `prefect` while preserving explicit `--runner local` fallback
- [x] 10.3 Post-flip verification:
  - [x] rerun majors/minors with `pipeline=both`
  - [x] rerun all-universe sharded batch
  - [x] verify idempotent rerun (`--skip-existing`) behavior

## 11. Default configuration simplification
- [x] 11.1 Update `.env.example` with recommended Prefect runtime defaults
- [x] 11.2 Align scanner settings defaults for simple CLI run path
- [x] 11.3 Verify scanner CLI defaults to Prefect in unit tests

## 7. Workflow quality improvements (next)
- [x] 7.1 Add optional idempotent skip (`workflows/prefect/run_batch.py --skip-existing`)
- [ ] 7.2 Improve batch chaining: per-run analytics begins as soon as its data completes (instead of global barrier)
- [ ] 7.3 Add lightweight metrics artifact (API calls, coverage, retry-after) for observability

## 8. Seamless CLI integration (no intermediate spec file)
- [x] 8.1 Add `--runner prefect` to `tvscreener-scan` (requires `uv sync --extra prefect`)
- [x] 8.2 Add a short runbook section showing the single-command usage

## 6. Scale readiness (next)
- [x] 6.1 Always write deterministic artifacts under `artifacts/runs/<params_hash>/`:
  - `run_spec.json`
  - `run_result*.json`
  - default `*_results.parquet` for analytics when `output` is not provided
- [x] 6.2 Add a batch runner that fans out runs across:
  - `asset_type`
  - `universe` / symbol shards
  - `timeframe_set_id`
  - `scanner_family`
- [x] 6.3 Add a “spec generator” helper (batch spec → list of `PipelineRunSpec`) for large-scale runs
- [x] 6.4 Add basic universe sharding into explicit `pairs` chunks (`max_pairs_per_run`)
- [x] 6.5 Add per-worker upstream rate limiting knobs for data runs (min interval + jitter)
- [x] 6.6 Add split concurrency controls (data vs analytics) for batch runs
