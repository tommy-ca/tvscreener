## Proposal: Refactor artifacts contract (minimal, rich, engine-agnostic)

### Context
The repo currently emits several flavors of “artifacts”:

- Engine-run artifacts under `artifacts/prefect/<params_hash>/` (Prefect runner)
  - `run_spec.json`
  - `run_result_data.json` / `run_result_analytics.json` / `run_result.json`
  - `<scanner_family>_results.parquet`
  - `matrix.txt` (when `matrix=true`)
- Batch summaries under `artifacts/prefect/batch/<batch_id>/`
  - `batch_meta.json`, `batch_result.json`
- Ad-hoc local logs under `artifacts/matrix/` (operator-created; not a stable contract)
- Validation artifacts under `artifacts/validation/` (operator-created)

This mix is workable but not clean:
- There are multiple “result JSON” flavors (stage-specific vs both), which complicates consumers.
- Some artifacts are engine-prefixed by directory name (`prefect`) even though the spec contract is engine-agnostic.
- The base directory can accumulate non-run files (e.g. top-level `.parquet` under `artifacts/prefect/`).

### Goal
Define and enforce a single, minimal, rich artifacts contract that:

- is engine-agnostic (local runner, Prefect, future engines)
- is deterministic (`params_hash` keyed)
- is self-describing for machine consumers
- avoids duplicated outputs (especially stage-specific result JSONs)
- supports optional “matrix view” text capture when requested

### Artifacts contract (v2)

Base directory: `artifacts/runs/` (engine-agnostic). For backwards compatibility, allow `artifacts/prefect/` as a legacy alias.

Per run dir: `artifacts/runs/<params_hash>/`

**Always**
- `run_spec.json` (normalized `PipelineRunSpec`)
- `run_result.json` (single result payload; always present)

**Analytics-only / both**
- `<scanner_family>_results.parquet` (default analytics result; required when analytics succeeds)

**Optional**
- `matrix.txt` (only when `matrix=true`)

Batch dir: `artifacts/runs/batch/<batch_id>/`
- `batch_result.json`

### Compatibility plan
- Support legacy reads of `run_result_data.json` / `run_result_analytics.json` for idempotent skips during transition.
- Prefer a single `run_result.json` for all pipeline modes.
- Add a maintenance command to prune deprecated files and relocate legacy dirs.

### Non-goals
- Do not store full execution logs as “artifacts” (use Prefect UI/log aggregation).
- Do not treat ad-hoc CLI log captures (e.g. `tee artifacts/matrix/...`) as a supported contract.
