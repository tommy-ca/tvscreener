# Project Context (project-local OpenSpec)

## Purpose
`tvscreener` is a Python library + CLI that queries TradingView screener endpoints and produces
actionable screening outputs. The project includes an **Iceberg lakehouse** (Bronze/Silver/Gold)
to support replayable pipelines, auditable signals, and fast edge analytics.

## Tech Stack
- Python (library + CLI)
- `uv` for dependency management and running commands
- Apache Iceberg via `pyiceberg` + `pyarrow`
- DuckDB for edge analytics (`EdgeQueryClient`)
- Narwhals for backend-agnostic dataframe transforms
- Pandas as the primary dataframe interchange
- `pytest` for tests
- `rich` for CLI rendering

## Architecture Patterns
- Medallion architecture: **Bronze** (raw ingestion) → **Silver** (standardization + identity) → **Gold**
  (features for serving).
- Multi-timeframe focus:
  - `timeframes` and `timeframe_set_id` are first-class keys for wide-form outputs.
  - long-form tables with a `timeframe` column are the preferred long-term representation.
- Separation of concerns:
   - **Data pipelines** (`pipeline_mode=data`) do ingestion + feature engineering and persist to Iceberg.
   - **Analytics pipelines** (`pipeline_mode=analytics`) do reporting: read Iceberg and write artifacts.

## Terminology
Canonical terminology and deterministic naming rules live in:
- `docs/openspec/changes/update-terminology-and-interfaces/specs/terminology/spec.md`

## Orchestration
Composable Prefect stage tasks live in:
- `docs/openspec/changes/refactor-prefect-composable-flows/specs/prefect-composition/spec.md`

## Packaging direction
- `tvscreener` is the upstream core library + CLI.
- Repo-local orchestration (Prefect scheduling, batch runners) and any custom screeners SHOULD be packaged as a
  separate extensions distribution that depends on the installed upstream `tvscreener`.
- Goal: workflows can run without cloning or patching upstream; local development can still use this repo.

Packaging reality check:
- If the package-index upstream does not ship the workflow/pipeline surface area (e.g. `tvscreener-scan`, pipeline
  runner, Prefect wrapper), extensions MUST own those layers or upstream must publish a compatible version.

## Conventions
- Favor canonical columns in persisted tables: `asset_type`, `entity_id`, `signal_date`,
  `run_id`, `fetched_at_utc`, `timeframes`, `timeframe_set_id`, `source`, `scanner_family`.
- Iceberg tables are canonical; on-disk snapshots are optional debug artifacts only.

## Workspace hygiene
- Keep repo-root noise low: generated outputs belong under `artifacts/` / `exports/` (both gitignored).
- Local runner state lives under `.prefect-home/` (gitignored); delete it to reset local Prefect state.
- Local lakehouse state can live under `.tvscreener/lakehouse/` (gitignored) when `TVSCREENER_LAKEHOUSE_BASE_DIR` is
  set for reproducible local/remote parity.
- Common safe cleanup (gitignored): `rm -rf __pycache__ .pytest_cache .ruff_cache build *.egg-info .prefect-home.bak-*`

Recommended:
- Use `scripts/clean-workspace.sh` for repeatable cleanup.
