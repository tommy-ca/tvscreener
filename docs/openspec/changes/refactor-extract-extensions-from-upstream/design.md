## Design: Extensions distribution (upstream-first)

### Overview
We split the project into:

- **Upstream core**: `tvscreener` (library + CLI; Iceberg lakehouse; scanners; data + analytics pipelines).
- **Extensions**: `tvscreener-ext` (workflow/orchestration + optional custom screeners), installed separately and
  importing the upstream core package.

### Constraints
- Extensions MUST NOT require cloning or patching upstream.
- Extensions MUST run with uv-native commands (no `pip`).
- When executed from a repo checkout, extensions MUST NOT accidentally import `tvscreener` from the local source tree.

### Upstream packaging reality check
At the time of writing (2026-03-25), the package index `tvscreener==0.2.1` ships a smaller surface area
(`tvscreener.core.*`, filters/fields, etc.) and does not ship the repo-local workflow/pipeline modules
(`tvscreener-scan`, `tvscreener.lib.*`, Prefect extras).

Implication:
- Either upstream must publish a version that includes the pipeline + CLI surface area expected by these workflows,
  OR the extensions distribution must own the orchestration + pipeline layers (Iceberg writes, DuckDB analytics)
  while using upstream `tvscreener` primarily for TradingView API access.

### Distribution layout (within this repo)
- `extensions/pyproject.toml`
- `extensions/src/tvscreener_ext/...`

### CLI model
Extensions provide operator-facing CLIs that wrap/parameterize upstream behavior:

- `tvscreener-ext-scan`: user entrypoint for running the essential universes under `--runner prefect`.
- `tvscreener-prefectctl`: consistent Prefect server + pool/queues/workers setup.
- `tvscreener-deploy-schedules`: schedule deployment definitions (runner or worker engine).

The upstream `tvscreener-scan` remains available for repo development, audits, and power-user workflows.

### Validation strategy
1) In-process Prefect execution (server + runner):
   - run `pipeline_mode=both` for each essential universe
   - ensure `run_result.json` shows `success=true` and results parquet exists
2) Worker-based execution (server + workers):
   - apply deployments
   - start `data` + `analytics` workers
   - confirm scheduled runs are queued and executed

### Two-track plan (rescheduled)

Track A (thin-wrapper extensions):
- Preconditions:
  - Upstream `tvscreener` package ships `tvscreener-scan` and the pipeline runner modules used by workflows.
- Extensions responsibility:
  - scheduling / orchestration / batch templates
  - upstream import resolution guards

Track B (extensions-owned pipelines):
- Preconditions:
  - Upstream `tvscreener` remains a lightweight TradingView client (`tvscreener.core.*`).
- Extensions responsibility:
  - implement `PipelineRunSpec` + runner
  - implement Iceberg persistence layer + DuckDB-backed analytics
  - implement Prefect flows on top of the extensions runner

Selected approach: Track B.

Implementation notes:
- Data pipeline uses upstream `tvscreener.core.{forex,crypto,stock}.*` screeners for the TradingView POST API.
- Extensions own table naming and persistence into an Iceberg catalog.
- Analytics pipeline reads from Iceberg and uses DuckDB as the query engine for producing results parquet and
  matrix artifacts.

Prefect note (worker engine):
- With Prefect 3, worker deployments require an explicit code distribution strategy.
- In practice, deployments applied from a local checkout (even with a module-path entrypoint and/or a
  `local-file-system` pull step) can remain `status=NOT_READY`.
- For local OSS server scheduling, `status=NOT_READY` alone is not a reliable signal; prefer validating via
  `tvscreener-prefectctl check` and confirming scheduled flow runs exist in the target work queue.
- For local single-machine execution, scheduled runs can still execute under a `process` worker even when the
  deployment status remains `NOT_READY`.
- Work-pool storage configuration is currently cloud-oriented (S3/GCS/Azure); there is no supported
  local-filesystem work-pool storage configuration for READY worker scheduling.
- Current operator fallback: use in-process Prefect execution (`--runner prefect`) for repeatable runs.
- Production path: adopt one of:
  - Docker-image deployments where the image contains the extensions code + deps, OR
  - a remote storage strategy compatible with Prefect work-pool storage.

Prefect note (local server):
- When using Prefect OSS server with SQLite, keep `PREFECT_HOME` isolated per repo and avoid running multiple
  Prefect servers against the same SQLite DB to prevent `database is locked` errors.

### Data/analytics correctness checks
- Data: Iceberg tables are updated in `pipeline_mode=data|both`.
- Analytics: outputs and matrix view are produced without upstream fetch and can be audited via DuckDB queries.

### Track B lakehouse contract (current)
- Writes:
  - `tvscreener.bronze` (append; long-form per timeframe)
  - `tvscreener.signals_latest` (overwrite scoped; partitioned by `asset_type`, `instrument_type`, `universe`)
  - `tvscreener.runs` (append; best-effort audit)
- Reads:
  - analytics loads from `tvscreener.signals_latest` only
- Note: legacy medallion tables (`tvscreener.silver`, `tvscreener.gold`, `tvscreener.signals_batch`) may exist from
  earlier implementations but are not required for Track B execution.

### Environment defaults (extensions)
- Prefect:
  - `TVSCREENER_PREFECT_WORK_POOL` default: `tvscreener`
  - `TVSCREENER_PREFECT_WORK_QUEUE` default: `default`
- Lakehouse:
  - `TVSCREENER_LAKEHOUSE_BASE_DIR` is the primary knob for keeping local and remote runs identical.
  - Default base dir (extensions): `.tvscreener/lakehouse` under the working directory.
