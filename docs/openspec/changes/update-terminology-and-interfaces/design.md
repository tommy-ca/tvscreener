# Design: Canonical vocabulary

## Principles
- Prefer Prefect-native nouns for orchestration: flow, deployment, work pool, work queue, worker, flow run, task run.
- Keep `PipelineRunSpec` stable; document semantics instead of renaming fields.
- Use deterministic identifiers for anything user-facing (deployment names, artifact keys, run directory keys).
- Treat Iceberg tables as the source of truth for pipeline outputs.

## Canonical stage semantics
We keep the existing `pipeline_mode` values but standardize their meaning:

- `pipeline_mode=data`:
  - DataOps + feature engineering stage
  - Fetch upstream snapshot(s)
  - Persist to Iceberg (raw/bronze + feature/serving tables)
- `pipeline_mode=analytics`:
  - Reporting stage
  - Read from Iceberg serving tables
  - Write filesystem artifacts (parquet + matrix markdown)
  - Optionally publish Prefect artifacts (markdown + table preview)
- `pipeline_mode=both`:
  - Execute `data` then `analytics` in the same logical run

## Canonical lakehouse products
- Raw table: `tvscreener.bronze` (append)
- Serving/feature view: `tvscreener.signals_latest` (overwrite scoped)
- Audit: `tvscreener.runs` (append; best-effort)

## Prefect mapping
- Flow: `tvscreener-batch` (executes one batch spec)
- Deployment: `tvscreener-batch/<deployment-name>`
- Work pool: `TVSCREENER_PREFECT_WORK_POOL` (default: `tvscreener`)
- Work queue: `TVSCREENER_PREFECT_WORK_QUEUE` (default: `default`)
- Worker: Prefect `process` worker for local runs; docker/remote worker for remote runs

## Deterministic naming
- Run directory key: `params_hash` (sha256 of canonical spec JSON)
- Filesystem artifacts live under: `artifacts/runs/<params_hash>/`
- Prefect artifact keys are deterministic and derived from `PipelineRunSpec`.
