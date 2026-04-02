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

## Zero-Fork Policy (Mandatory)
- **Goal:** This repository MUST NOT maintain a local fork of `tvscreener`.
- **Dependency:** `tvscreener` is treated as an external library resolved from `site-packages`.
- **No Local Source:** The `tvscreener/` source tree has been removed from the repository to prevent shadowing and accidental local patching.
- **Workflow Isolation:** All orchestration, lakehouse persistence, analytics, and custom screeners reside in `extensions/src/tvscreener_ext/`.
- **Import Guard:** Extension entry points call `ensure_upstream_tvscreener()` to verify resolution from `site-packages`.
- **Verification:** All validation runs against the installed upstream package.

Packaging reality check:
- If the package-index upstream does not ship the workflow/pipeline surface area (e.g. `tvscreener-scan`, pipeline
  runner, Prefect wrapper), extensions MUST own those layers or upstream must publish a compatible version.

## Conventions
- **Verification Standard:**
  - **Unit Tests:** `uv run python -m pytest tests/` (verified against site-packages).
  - **Orchestration:** `uv run --project extensions tvscreener-ext-validate --runner prefect` (requires Prefect server + worker).
  - **Prefect Table Artifacts:** Prefect runs SHOULD publish table artifacts for key outputs (Opportunities/Signals) to enable in-browser data review. This is controlled via the `TVSCREENER_PUBLISH_TABLE_ARTIFACTS=1` environment variable.
  - **Import Audit:** `uv run --project extensions python extensions/tools/check_upstream_tvscreener_resolution.py`.
  - **Pure Upstream:** `git diff v0.2.1 -- tvscreener/` MUST be empty or only contain non-logic files.
- **Testing & Mocking:**
  - **Extension Imports:** Test modules relying on extension patches MUST explicitly import the extension module (`import tvscreener_ext`), ensuring mock validations override external boundaries.
  - **Data Shape Validation:** API and dataframe mocks must accurately reflect the library's implicit row/column augmentations (e.g. prepended structural identifiers like `Symbol`).
  - **Enum Subclasses:** Magic method patches (`__eq__`, `__gt__`) applied to base Enums must iterate through all active subclasses (`FieldWithInterval`, `FieldWithHistory`) and evaluate equivalence using rigid literal criteria to avoid truthy collision bugs in filter aggregations.
- Favor canonical columns in persisted tables: `asset_type`, `entity_id`, `signal_date`,
  `run_id`, `fetched_at_utc`, `timeframes`, `timeframe_set_id`, `source`, `scanner_family`.
- Iceberg tables are canonical; on-disk snapshots are optional debug artifacts only.

## Repository Layout Constraints (SOLID, KISS, DRY, YAGNI)
- **SOLID / YAGNI**: The repository must contain only what is strictly necessary to test and deploy the pipeline extensions (`extensions/`, `tests/`, `docs/`, `scripts/`). Experimental apps (`app/`), deprecated scripts (`.dev/`), redundant submodules (`semantic/`), and obsolete workflows must be removed immediately to prevent dead code accumulation.
- **KISS**: All pipeline orchestration, edge analytics, lakehouse storage, and custom screeners are strictly consolidated into `extensions/src/tvscreener_ext/`. Avoid scattering logic across multiple root-level directories.
- **DRY**: Rely exclusively on the installed upstream `tvscreener` package. Do not duplicate upstream source code, and avoid over-patching upstream logic if the upstream implementation is sufficient (e.g., `set_symbol_types` resolution).
- **Workspace Structure**: The project root MUST be configured as a `uv` workspace root with `package = false`. It MUST NOT claim to be the `tvscreener` package to avoid shadowing the upstream dependency.

## Continuous Review & Refinement
- **Issue Spotting**: Regularly run static analysis tools (`ruff`, `ty`) to identify architectural drift, dead code, or type safety regressions.
- **Refactoring Candidates**: Large modules (e.g. `orchestrator.py` > 50KB) should be periodically evaluated for decomposition following SOLID principles.
- **Documentation Parity**: Design documents and specifications must be updated to remove references to deleted legacy components or defunct paths.

## Technical Debt & Refactoring (Audited 2026-04-01)
- **Service Decomposition**: The monolithic `ScreenerController` is being refactored into specialized services defined in `docs/architecture/SERVICES.md`.
- **Monolithic Controller**: `ScreenerController` in `orchestrator.py` (~1.6k LOC) MUST be decomposed into specialized services to satisfy SRP and improve testability:
    - **`UniverseResolver`**: Decouples symbol discovery from execution. Responsible for resolving asset types, aliases, and dynamic universes (e.g. Binance).
    - **`ConfigFactory`**: Translates the public `ScanRequest` API into internal engine configurations (`ForexScreenerConfig`, `StrategyConfig`).
    - **`ExportService`**: Centralizes IO and metadata handling, ensuring consistent artifact generation across CSV, JSON, and Parquet.
    - **`ReportingService`**: Dedicated logic for universe audits, historical reports, and validation reviews.
    - **`ScanWorkflow`**: Coordinates the high-level execution lifecycle (Discovery -> Config -> Fetch -> Filter -> Export).
- **CLI Boilerplate**: `scan.py` should be refactored to use a command-registry pattern to reduce `argparse` overhead and enforce consistent subcommand interfaces.
- **Stale Documentation**: Historical specifications in `docs/openspec/changes/` must be audited and marked with a `LEGACY` header to avoid confusion with the current Zero-Fork architecture.

## Workspace hygiene
- Keep repo-root noise low: generated outputs belong under `artifacts/` / `exports/` (both gitignored).
- Local runner state lives under `.prefect-home/` (gitignored); delete it to reset local Prefect state.
- Local lakehouse state can live under `.tvscreener/lakehouse/` (gitignored) when `TVSCREENER_LAKEHOUSE_BASE_DIR` is
  set for reproducible local/remote parity.
- Common safe cleanup (gitignored): `rm -rf __pycache__ .pytest_cache .ruff_cache build *.egg-info .prefect-home.bak-*`

Recommended:
- Use `scripts/clean-workspace.sh` for repeatable cleanup.
