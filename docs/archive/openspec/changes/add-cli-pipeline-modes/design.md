# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: CLI pipeline modes (data vs analytics)

### Goals
- Allow rerunning **matrix views** from Iceberg without refetching upstream data.
- Keep data pipelines canonical and query-backend independent.
- Make “strategy scanning” an analytics pipeline that consumes Iceberg-backed Gold rows.

### Non-goals (for this change)
- Introduce new Iceberg tables for strategy outputs (e.g. `tvscreener_product.strategy_signals_latest`).
- Rework medallion schemas; this change consumes the existing `tvscreener.{bronze,silver,gold,signals_latest}` tables.

### CLI contract
Add `--pipeline` to `tvscreener-scan`:
- `--pipeline data`: run the data pipeline only (fetch + persist).
- `--pipeline analytics`: run the analytics pipeline only (query Iceberg + render).
- `--pipeline both` (default): run data pipeline then analytics pipeline on the persisted outputs.

Runner notes:
- Default runner is Prefect (`--runner prefect`), backed by a Prefect server (`PREFECT_API_URL`).
- `--runner local` is an explicit fallback; it executes via the `PipelineRunSpec` contract and persists `tvscreener.runs` metadata.

Logging notes:
- When running with Prefect (recorded console), progress spinners are disabled to avoid noisy `Fetching data...` frame spam in logs.

### Source of truth for analytics
- Opportunity matrix view reads from: `tvscreener.signals_latest`
- Strategy matrix view reads from: `tvscreener.signals_latest`, then computes strategy signals in-memory.

This ensures the matrix view is always reproducible from the Iceberg lakehouse.

### Analytics query shape (forex)
Analytics runs need the same user-facing selectors as scans:
- `--asset-type forex`
- `--universe majors|minors|all` (or `--pairs ...`)
- `--timeframes 240,60,15` (drives `timeframe_set_id`)

Implementation uses DuckDB (`EdgeQueryClient`) to query Iceberg tables and returns a pandas DataFrame to existing renderers.
