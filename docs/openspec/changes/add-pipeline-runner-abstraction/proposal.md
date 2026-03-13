# Change: Pipeline runner abstraction (external workflow engines)

## Why
The repo now supports a split between **data pipelines** (fetch → Iceberg) and **analytics pipelines**
(Iceberg → matrix view). Execution is currently tied to the in-process CLI/orchestrator.

To scale scans (parallelism, retries, SLAs, scheduling, distributed workers) we need to decouple:
- **Pipeline definition** (what to run; deterministic; serializable)
- **Pipeline execution** (how to run; local vs external workflow engines)

This enables operators to opt into external workflow engines (Prefect/Dagster/Temporal/Airflow/Argo/etc.)
without the core library importing or depending on those engines.

## What changes
- Introduce a **`PipelineRunSpec`** contract (JSON-serializable) that fully describes a scan run:
  - scanner family (`opportunity`/`strategy`)
  - pipeline mode (`data`/`analytics`/`both`)
  - asset selection (`asset_type`, `universe`, `pairs`)
  - multi-timeframe (`timeframes`, `timeframe_set_id`)
  - filters/params (`strategy`, `sql`, `filters`, thresholds)
  - config pointer (`config_path`) and reproducibility fields (`params_hash`, optional `code_version`)
- Introduce a **`PipelineRunner` interface**:
  - `run(spec) -> RunResult` for synchronous execution (local)
  - (future) adapters MAY add non-blocking submission/status APIs, but the baseline contract is synchronous `run(spec)`
- Keep the default CLI behavior using a **PrefectRunner** (post-flip), with explicit `--runner local` fallback.
- Add a **lightweight opt-in** hook to integrate workflow engines without adding core dependencies:
  - `--runner local` (default)
  - `--runner export` (emit `PipelineRunSpec` JSON to stdout/file for external submission)
  - (future) `--runner http --runner-url ...` or similar adapter

## Lightweight workflow engine integration (non-goal for core deps)
Workflow engines should treat `PipelineRunSpec` as the engine’s **run configuration payload**:
- Dagster: run config / resources inputs
- Prefect: flow parameters (optionally use `params_hash` as a cache key)
- Temporal: workflow input (activities perform IO)

This repo will provide optional **wrapper scripts/examples** that live *outside* the core `tvscreener` library package,
so installing the base library does not pull in workflow-engine dependencies.

## Impact
- Library becomes more reusable: external orchestration systems can call `tvscreener` as a pure “task library”.
- CLI becomes an adapter: it builds `PipelineRunSpec` and delegates to a runner.
- No hard dependency on any workflow engine is introduced.
