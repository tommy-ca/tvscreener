# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Minimal artifacts contract (v2)

### Problem statement
Artifacts today are useful but fragmented:
- multiple result JSON types depending on pipeline mode
- engine-prefixed base directories (`artifacts/prefect/`)
- ad-hoc operator log captures living next to contract artifacts

The result is: machine consumers need special cases and humans aren’t sure which files matter.

### Design principles
- **Minimal**: only persist what downstream consumers need.
- **Rich**: the primary JSON should contain enough context to reproduce and audit.
- **Deterministic**: stable locations keyed by `params_hash`.
- **Engine-agnostic**: artifacts describe the run, not the orchestrator.

### Canonical layout

Base dir: `artifacts/runs/`

Run dir: `artifacts/runs/<params_hash>/`

Files:
- `run_spec.json`
- `run_result.json`
- `<scanner_family>_results.parquet` (analytics success)
- `matrix.txt` (only when `matrix=true`)
- `results_top_rows.json` (DuckDB semantic; analytics success)
- `results_grade_summary.json` (DuckDB semantic; analytics success)

Batch dir: `artifacts/runs/batch/<batch_id>/`
- `batch_result.json`

### `run_result.json` payload (shape)

Single payload regardless of `pipeline_mode`:
- `spec_version`, `params_hash`, `scanner_family`, `asset_type`, `universe`, `timeframes`, `timeframe_set_id`
- `code_version`
- `pipeline_mode_requested`, `pipeline_mode_executed`
- `started_at_utc`, `finished_at_utc`, `success`, `exit_code`, `result_count`, `errors`
- `artifacts_dir`
- `results_path` (when analytics ran)
- `matrix_path` (when matrix was captured)
- `lakehouse` pointers (table names used; optional snapshot identifiers when available)

The goal is to avoid requiring consumers to read logs to find what was produced.

### Current implementation note (2026-03-25)
The on-disk `run_result.json` payload is currently optimized for pipeline replay and quick inspection:

- Top-level fields include:
  - `spec_version`, `params_hash`, `scanner_family`
  - `pipeline_mode_requested`, `pipeline_mode_executed`
  - `artifacts_dir`, `run_spec_path`, `run_result_path`
  - `results_path` (when analytics executed)
  - `matrix_path` (when matrix executed and captured)
  - `success`
- Pipeline stage payloads are nested:
  - `data` for data-only and both-mode runs
  - `analytics` for analytics-only and both-mode runs (includes `results_path`)

This differs from the target “single flat payload” shape above; consumers should treat the schema as v2 and rely on
the stable paths (`run_spec.json`, `run_result.json`, `matrix.txt`, `*_results.parquet`) rather than stage-specific JSON
filenames.

### Prefect artifacts note
Prefect Table artifacts require JSON-serializable cell values.

- Coerce numpy/pandas scalars to Python primitives.
- Coerce datetimes to ISO-8601 strings before publishing.

### Migration
- Introduce `artifacts/runs/` as the canonical default.
- Keep `artifacts/prefect/` working as a legacy base dir for a transition window.
- Add a prune/migrate maintenance routine to:
  - relocate `artifacts/prefect/<params_hash>/` -> `artifacts/runs/<params_hash>/`
  - delete deprecated stage-specific JSONs once `run_result.json` exists
  - flag unexpected top-level files under the base dir
