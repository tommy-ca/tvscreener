# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Prefect scheduled batch runs

### What runs on a schedule

We schedule the `tvscreener-batch` Prefect flow (`workflows/prefect/run_batch.py`) with a `batch_path` parameter.

Flow run naming note:
- `flow_run_name` templates must reference flow parameters; using computed locals (like `batch_id` derived from JSON)
  can crash worker execution with `KeyError` during flow run context setup.

Operator note:
- Prefect may assign whimsical flow run names; use `flow_run_id` for deterministic references in docs and tooling.

Default scheduling behavior: **data pipelines only**.

Terminology note:
- `pipeline_mode=data` is ingestion + feature engineering (Iceberg writes).
- `pipeline_mode=analytics` is reporting (Iceberg reads + artifact writes).

Analytics runs can be:
- invoked on demand (recommended), or
- scheduled as `pipeline_mode=both` to run analytics immediately after data.

### Strict persistence for scheduled data runs

Scheduled data runs enable strict persistence so Iceberg write failures fail the run instead of being swallowed.

This is implemented by setting `TVSCREENER_STRICT_PERSIST=1` for Prefect batch and single-run data tasks.

Strict persistence also applies to appending the audit row in `tvscreener.runs`.

### Analytics validation (post scheduled data)

After a scheduled data run completes, validate by rerendering the matrix from Iceberg:

If running in extensions-owned pipeline mode (Track B), prefer `tvscreener-ext-scan` / `tvscreener-ext-validate`
instead of repo-local `tvscreener-scan`.

Track B example (rerender analytics from Iceberg):

```bash
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run --project extensions --extra prefect tvscreener-ext-scan \
    --runner prefect --scanner opportunity --pipeline analytics \
    --asset-type forex --universe majors --timeframes 15,60,240 --matrix --limit 50 --config tvscreener.yaml
```

```bash
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe majors --timeframes 15,60,240 --pipeline analytics --matrix --config tvscreener.yaml
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe minors --timeframes 15,60,240 --pipeline analytics --matrix --config tvscreener.yaml

PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 15,60,240 --pipeline analytics --matrix --config tvscreener.yaml
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 15,60,240 --pipeline analytics --matrix --config tvscreener.yaml
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 15,60,240 --pipeline analytics --matrix --config tvscreener.yaml
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 15,60,240 --pipeline analytics --matrix --config tvscreener.yaml

PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type stock --universe market_risk --timeframes 15,60,240 --pipeline analytics --matrix --config tvscreener.yaml
```

Freshness note:
- Data-only schedules (`pipeline_mode=data`) will not update analytics artifacts (`opportunity_results.parquet`, `matrix.txt`).
- Before rerendering, verify the most recent successful `pipeline_mode_executed='data'` run is recent for the target universe.

Write semantics note:
- Analytics runs are read-only with respect to the medallion/product tables used for signals (e.g. `signals_latest`).
- Analytics runs still append audit metadata to `tvscreener.runs`.

Recommended operator policy:
- Treat data as "fresh" when the latest successful `pipeline_mode_executed='data'` run is within the last 60 minutes.
- If stale, trigger the `*-data` deployments via a Prefect worker, then rerender analytics.

Prefect 3 worker scheduling note (Track B):
- Worker-based scheduled flow runs require a Prefect-compatible code distribution strategy.
- Without remote storage (S3/GCS/Azure) or a container image that includes the extensions code, deployments can
  remain `status=NOT_READY`.
- In local OSS server mode, schedules can still materialize flow runs even when deployments are `NOT_READY`.
  If `scheduled_runs=count 0`, it is often due to server/scheduler issues (server not running, scheduler disabled,
  or SQLite lock contention) rather than the deployment status alone.
- Local fallback: run the essential runset in-process under Prefect (`tvscreener-ext-validate --runner prefect`).

Prefect server reliability note (local SQLite):
- When running Prefect OSS server on SQLite, concurrent server/worker/runner processes sharing the same
  `PREFECT_HOME` can hit `database is locked` errors.
- Operator recovery: stop all Prefect processes and reset `PREFECT_HOME` (move `.prefect-home/` aside and start
  fresh).

Concurrency note:
- Iceberg writes use optimistic concurrency; concurrent runs can conflict ("branch main has changed").
- Prefer serial execution for writers: Prefect worker `--limit 1` and batch `data_concurrency=1`.

Environment defaults (extensions):
- `TVSCREENER_PREFECT_WORK_POOL` default: `tvscreener`
- `TVSCREENER_PREFECT_WORK_QUEUE` default: `default` (recommended)
- `TVSCREENER_LAKEHOUSE_BASE_DIR` should be set (recommended: `.tvscreener/lakehouse`) so workers read/write the
  same Iceberg catalog/warehouse across local and remote deployments.

Recommended deployment split:
- Data deployments per universe/instrument, followed by analytics deployments that publish Prefect artifacts.
- This reduces Iceberg write contention and makes failures easier to rerun.
- For local/remote parity, keep the split deployments on the `default` work queue.

Artifacts (Prefect UI):
- Matrix markdown: published as a markdown artifact when `TVSCREENER_PUBLISH_RESULTS_SUMMARY=1`.
- Results preview: published as a table artifact when `TVSCREENER_PUBLISH_TABLE_ARTIFACTS=1`.

Composable flow note (extensions):
- The `tvscreener-batch` flow uses stage tasks for `pipeline_mode=data` and `pipeline_mode=analytics`.
- Optional: set `TVSCREENER_PREFECT_COMPOSE_BOTH=1` to compose `pipeline_mode=both` from the stage tasks.

Example audit queries:
```bash
uv run tvscreener-scan query tvscreener.runs --sql "SELECT asset_type, universe, instrument_type, pipeline_mode_executed, success, result_count, started_at_utc FROM df WHERE pipeline_mode_executed='data' ORDER BY started_at_utc DESC LIMIT 12"

# Optional: verify a few key symbols are fresh in the analytics read-path.
uv run tvscreener-scan query tvscreener.signals_latest --sql "SELECT entity_id, strftime(fetched_at_utc,'%Y-%m-%d %H:%M:%S') AS fetched_at_utc, params_hash FROM df WHERE entity_id IN ('BINANCE:BTCUSDT','BINANCE:ETHUSDT') ORDER BY fetched_at_utc DESC LIMIT 10"
```

Validation snapshot (2026-03-25, Prefect server at `PREFECT_API_URL=http://127.0.0.1:4200/api`):

- Analytics-only rerender (read-only against medallion/product tables; writes artifacts + appends `tvscreener.runs`):
  - Forex majors: `artifacts/runs/70696cd35fb6f9f781e621a79fe0df995e70adb6925ed81052ba9aaad8fcc890/run_result.json`
  - Forex minors: `artifacts/runs/2ed6f942ae981b9c26606953e7a5a679efc1ed5526bbae63953cebc35517393f/run_result.json`
  - Crypto spot majors: `artifacts/runs/b966754797cb6428bfe242b903c82119bcd923224be60299f8c3c8c6883d1e8e/run_result.json`
  - Crypto perp majors: `artifacts/runs/02cdbd5ea6d54772f41e63878f3ece1df983038d485d12daf1d44212a99d984b/run_result.json`
  - Crypto spot minors: `artifacts/runs/3f18bd080d54f2118eeee02be0f79f9eab605cfe95d8977de244d7051a577388/run_result.json`
  - Crypto perp minors: `artifacts/runs/6b1f70993b3d2628e7f67014a74e41b1d6073ebc1c038fd18153e89bee97d5ed/run_result.json`
  - Market risk basket: `artifacts/runs/504ad7c6595b6e54d95243e9919d623e0bc7503acb42151fa5eab432c28dbaf1/run_result.json`

- Full refresh `pipeline_mode=both` (fetch -> Iceberg writes -> DuckDB-backed analytics render; strict persist enabled):
  - Forex majors: `artifacts/runs/b0621cdacfc9e3f4c2180c479b9cba5f6132525c33f83e512c440caea350fb0d/run_result.json`
  - Forex minors: `artifacts/runs/b5f5d2522b7ce46250203f4e81e86079fb2287f630b73e289407a3f2cf090c09/run_result.json`
  - Crypto spot majors: `artifacts/runs/08612e192e148ce072ef2c3cd070fb932b200f445d41662cfd0506f11a44672f/run_result.json`
  - Crypto perp majors: `artifacts/runs/d2a32c39ba1c443342705ac45c3befc996917c8b08c25d437743728f3404bec3/run_result.json`
  - Crypto spot minors: `artifacts/runs/676161ff4943e75fdeb2eabf6dc440b19fe5edf24b63e2db216aebffa53febfa/run_result.json`
  - Crypto perp minors: `artifacts/runs/b21f48952ba7b6efa086281ac58b87b6fd05662a1b8abc65aec9ed2e02c9c6d6/run_result.json`
  - Market risk basket: `artifacts/runs/742c343a8e2440a17409d1fbe6e6f332ec71998f9dd4c575c850a0414dad8b2e/run_result.json`

Artifact contract:
- Per run (`artifacts/runs/<params_hash>/`):
  - `run_spec.json` (always)
  - `run_result.json` (always)
  - `matrix.txt` (when `--matrix` is enabled)
  - `<scanner_family>_results.parquet` (analytics/both; when output is not explicitly configured)
  - `universe.json` (best-effort; when universe resolution writes a snapshot and `TVSCREENER_RUN_DIR` is set)
- Per batch (`artifacts/runs/batch/<batch_id>/`):
  - `batch_meta.json`
  - `batch_result.json`

Prefect UI artifacts:
- When running under Prefect, each run spec publishes a single Markdown artifact (versioned by a stable key).
- Key format (approx): `tvscreener-matrix-<scanner>-<asset_type>-<instrument_type?>-<universe?>-<timeframe_set_id?>`.
- Key parts are sanitized (lowercase; non-`[a-z0-9-]` characters replaced with `-`).

Prefect UI tables:
- By default, run specs do not publish per-run Table artifacts (to reduce duplication with the Markdown artifact).
- To opt in, set `TVSCREENER_PUBLISH_TABLE_ARTIFACTS=1`.
- Table source:
  - Prefer an Iceberg query over `tvscreener.signals_batch` filtered by the corresponding `data` params hash.
  - Fall back to reading the per-run parquet output if the Iceberg query fails.
- Summary table:
  - The flow can publish a `-summary` table keyed like `tvscreener-results-...-summary` with counts/averages grouped by `GRADE` and `DIRECTION`.
  - To reduce Prefect artifact noise, it is disabled by default; set `TVSCREENER_PUBLISH_RESULTS_SUMMARY=1` to enable.

### Artifact audit (analytics table)

Current state (validated via the Prefect API `/api/artifacts/<key>/latest`):
- The `tvscreener-results-...` Table artifacts are stable at 23 columns across forex/crypto/market-risk.
- Forex includes `RVOL` and `Volume`; some universes may have `RVOL=null`.

ROC audit note:
- If `ROC_SCORE` appears as `0.0` while raw `ROC_15/ROC_60/ROC_240` are non-zero, that indicates a canonicalization mismatch.
- The scoring engine computes `ROC_SCORE` from ROC columns; ensure it recognizes canonical `ROC_<tf>` columns as well as raw TradingView columns like `Roc|<tf>`.
- If the scoring logic changes, rerun the `data` deployment to refresh `signals_batch` before expecting new values in analytics table artifacts.

Implementation note:
- The Prefect CLI `prefect artifact inspect ... -o json` output is not strict JSON (contains literal newlines in string values).
- For machine parsing/audits, prefer the Prefect API endpoints.

### Semantic layer (exploration)

Goal:
- Define shared dimensions and measures/metrics so table artifacts, DuckDB queries, and any future dashboards use the same definitions.

Non-goals (for now):
- Replace the existing scan pipeline logic.
- Introduce mandatory always-on services for local runs.

Candidate libraries:
- `sidequery/sidemantic`: Python-first semantic/metrics layer with DuckDB support and adapters for Cube + MetricFlow + other formats.
- `dbt-labs/metricflow`: semantic metric compiler intended to run alongside dbt projects.
- `cube-js/cube`: full semantic-layer runtime + APIs (more infra; strongest when you want a long-running service).

Note on "BSL":
- Sidemantic supports "BSL" as a semantic model format.
- If "bsl" refers to a specific runtime/library (not a model format), it needs separate evaluation.

Recommended starting point (low-infra):
- Evaluate Sidemantic first because it natively supports DuckDB and can sit next to this repo without requiring dbt or a dedicated server.

Sidemantic notes:
- Sidemantic is AGPL-3.0; confirm licensing is acceptable before adopting it in-repo.
- If licensing is a blocker, keep semantic definitions in `semantic/` and continue executing via DuckDB (EdgeQueryClient) until an alternative runtime is selected.

Integration audit (Sidemantic)

Reality check:
- Our Iceberg access path is via `pyiceberg` -> Arrow -> DuckDB in-process (see `tvscreener/lib/query.py`).
- Sidemantic expects to query a database connection (e.g. DuckDB) and read from real tables/views.
- Therefore, an integration needs a small runtime layer that exposes Iceberg tables to the Sidemantic DuckDB connection (either by materializing to DuckDB tables/views or by routing Sidemantic SQL through the existing EdgeQueryClient).

Recommended integration shape (minimal infra):
1) Keep semantic definitions in `semantic/models/*.yml`.
2) Provide a `SemanticLayer` wrapper that uses DuckDB and registers:
   - `tvscreener.runs` as a relation
   - `tvscreener.signals_batch` (and optionally `signals_latest`) as a relation
3) Use Sidemantic for:
   - validating the semantic definitions (`sidemantic validate semantic/models`)
   - generating standardized queries for Prefect table artifacts

Acceptance criteria:
- Prefect results tables are generated from semantic queries (not from ad-hoc column lists).
- Semantic validation can run in CI (non-interactive).
- The semantic runtime does not require a long-running service for local usage.
- Artifact schemas are stable across semantic runtimes (Sidemantic vs SQL fallback).

License gate:
- Do not add `sidemantic` as a required dependency unless AGPL-3.0 is explicitly accepted.

Enablement:
- Install: `uv sync --extra semantic`
- Default runtime: if Sidemantic is installed, it is used automatically.
- Force runtime:
  - `export TVSCREENER_SEMANTIC_RUNTIME=sidemantic`
  - `export TVSCREENER_SEMANTIC_RUNTIME=sql`

Current usage (in Prefect artifacts):
- Top rows + health/lineage prefer the semantic runtime when Sidemantic is installed, and fall back to the built-in DuckDB/Iceberg SQL path on errors.
- Grade summary prefers the semantic runtime when Sidemantic is installed, and falls back to SQL on errors.

Semantic layer shape:
- Semantic models define stable artifact surfaces (dimensions/aliases) so Prefect payload schemas do not drift between Sidemantic and SQL.
- The Sidemantic adapter is slice-based (materialize only the needed `params_hash` subset into a temp DuckDB file) to avoid requiring a direct Iceberg-to-Sidemantic integration.

Python compatibility:
- Sidemantic currently requires Python >= 3.11.

Evaluation criteria (audit):
- Works locally with DuckDB and the existing Iceberg tables.
- Models are versioned in git and validated in CI.
- Can express shared dimensions/measures for both:
  - operational dashboards (`tvscreener.runs`), and
  - decision dashboards (opportunity analytics / signals tables).
- Minimal infra: prefer CLI/library mode first; add a server only if needed.
- Licensing is acceptable.

Proposed semantic entities

1) `runs` (operational)
- Source: Iceberg table `tvscreener.runs`.
- Dimensions:
  - `started_at_utc` (time)
  - `asset_type`, `instrument_type`, `universe`
  - `pipeline_mode_executed`, `success`
  - `code_version`, `params_hash`
- Measures:
  - `run_count`
  - `success_rate`
  - `avg_result_count`
  - `p50_runtime_seconds`, `p95_runtime_seconds` (if duration is recorded)
  - `freshness_minutes` (computed relative to now)

2) `opportunity_signals` (decision surface)
- Preferred source: Iceberg product/gold table used by analytics reads (e.g. `tvscreener.signals_latest`) rather than per-run parquet artifacts.
- Dimensions:
  - `fetched_at_utc` / `signal_date` (time)
  - `asset_type`, `instrument_type`, `universe`, `venue`
  - `PAIR` (or `entity_id`), `Name`
  - `DIRECTION`, `GRADE`, `CONFLUENCE_LEVEL`
  - `timeframe_set_id`
- Measures:
  - `opportunity_count`
  - `count_by_grade` / `share_by_grade`
  - `count_by_direction`
  - `avg_ensemble_score`, `avg_total_confluence`
  - `top_n_by_total_confluence`

Bridging note:
- Until the Iceberg decision table is modeled, Prefect "results" Table artifacts can continue to be derived from the per-run parquet outputs.
- The target end-state is to compute those tables from semantic queries over Iceberg so the same definitions power artifacts and dashboards.

Proposed next steps:
1) Identify a minimal semantic model for `tvscreener.runs` (freshness, success rate, runtime) and for analytics outputs (counts by grade/direction, top-N by confluence).
2) Choose an initial storage for semantic definitions (recommended: `semantic/` directory in this repo).
3) Implement a thin wrapper that can execute semantic queries via DuckDB against Iceberg tables.
4) Switch Prefect table artifacts to be generated from semantic queries (not raw parquet reads) once the model is stable.

Model audit (non-interactive):
```bash
uv sync --extra semantic
uv run python3 semantic/audit_sidemantic.py
```

Note:
- `uv run sidemantic validate` launches an interactive TUI and is not suitable for CI.

Semantic model files (initial draft):
- `semantic/models/tvscreener_runs.yml`
- `semantic/models/opportunity_matrix.yml`

Semantic model note (matrix):
- `semantic/models/opportunity_matrix.yml` includes measures derived from the same columns that power the matrix (TREND/MA/OSC/ROC across timeframes, plus grid/confluence/grade).

DuckDB report artifacts (optional):
- For quick ops dashboards, you can query Iceberg tables (DuckDB) and publish the result as a Prefect Table artifact.
- Example: build a table from `tvscreener.runs` (data freshness and latest analytics rerenders) and publish it with `prefect.artifacts.create_table_artifact`.

Prefect batch artifacts:
- Prefect batch runs also publish a Table artifact summarizing the batch results.
- Key format: `tvscreener-batch-<batch_id>`.

`params_hash` note:
- `params_hash` is derived from a normalized `PipelineRunSpec`.
- Ordering of list fields matters (e.g. `timeframes`); keep `timeframes` in a stable order (recommended: `15,60,240`) to keep `params_hash` stable across reruns.

Latest validated matrices:
- `artifacts/runs/1f50f646cea5137a7e04bbf5522c37d66ed53d3062a9026bc35dd52e2db35c12/matrix.txt` (forex majors)
- `artifacts/runs/4d1eb4623dfa4c0c6cd0c1aab4b921375791550a22fbe89c795357b2463db4ac/matrix.txt` (forex minors)
- `artifacts/runs/9adf553aa50ec0199b011c42eceb2bc50aecc644341ff034e6251b64a535f4a0/matrix.txt` (crypto spot majors)
- `artifacts/runs/fc028529c86cec8a39ec06ba3de6f2e80d1c874f82822138d1fa0bff2ea2d70b/matrix.txt` (crypto perp majors)
- `artifacts/runs/16b92a50cd3a9b8e126eba053ca59ed6eb22e8e85e3c035c8d1b46da99ee1a1e/matrix.txt` (crypto spot minors)
- `artifacts/runs/31e6057e79b0a3b7662236c4ab6f1d57c3617ac69dbc6b484ff26ad6946d7ccc/matrix.txt` (crypto perp minors)
- `artifacts/runs/46da8bfeeb4e08e27d03fff43c442eb8e6a47c5e692541ff1c01cb6efffa054a/matrix.txt` (market risk)

Validated at (UTC):
- Data freshness validated via `tvscreener.runs`; latest `pipeline_mode_executed='data'` start times:
  - forex majors: 2026-03-19 15:15:16
  - forex minors: 2026-03-19 15:17:48
  - crypto majors spot: 2026-03-19 15:13:42
  - crypto majors perp: 2026-03-19 15:25:57
  - crypto minors spot: 2026-03-19 15:28:33
  - crypto minors perp: 2026-03-19 15:31:13
  - market risk: 2026-03-19 15:30:09
- Analytics matrices rerendered from Iceberg at:
  - forex majors: 2026-03-19 15:27:27
  - forex minors: 2026-03-19 15:28:42
  - crypto majors spot: 2026-03-19 15:30:30
  - crypto majors perp: 2026-03-19 15:31:47
  - crypto minors spot: 2026-03-19 15:33:14
  - crypto minors perp: 2026-03-19 15:34:37
  - market risk: 2026-03-19 15:37:08

Validation note:
- Verified scheduled `data` runs were recent (within the last hour) before rerendering the analytics matrices.
- Verified analytics rerenders wrote `matrix.txt` and appended `pipeline_mode_executed='analytics'` rows to `tvscreener.runs`.

Batch specs:
- `workflows/prefect/batches/forex_majors_minors_both.json` (existing)
- `workflows/prefect/batches/forex_majors_minors_data.json`
- `workflows/prefect/batches/forex_majors_minors_analytics.json`
- `workflows/prefect/batches/forex_majors_minors_opportunity_analytics.json`
- `workflows/prefect/batches/crypto_binance_majors_minors_both.json`
- `workflows/prefect/batches/crypto_binance_majors_minors_data.json`
- `workflows/prefect/batches/crypto_binance_majors_minors_analytics.json`
- `workflows/prefect/batches/market_risk_proxy_both.json`
- `workflows/prefect/batches/market_risk_proxy_data.json`
- `workflows/prefect/batches/market_risk_proxy_analytics.json`

### Apply schedules

1) Start a Prefect server:
```bash
export PREFECT_HOME="$PWD/.prefect-home"
uv run prefect server start --host 127.0.0.1 --port 4200 --background
export PREFECT_API_URL="http://127.0.0.1:4200/api"
```

2) Create a process work pool (once):
```bash
uv run prefect work-pool create --type process tvscreener
```

3) Start a worker (blocks; keep it running):
```bash
uv run prefect worker start --pool tvscreener
```

Worker note:
- The `process` work pool uses a temp working directory by default.
- These deployments set `job_variables.working_dir` to the repo root so file-path entrypoints like `workflows/prefect/run_batch.py:run_batch` can be imported.
- Prefect `process` workers do not fetch/clone code; the repo must already exist at `job_variables.working_dir` on the worker host.

4) Register deployments (cron schedules) for workers:
```bash
uv run python3 workflows/prefect/deploy_schedules.py --apply --engine worker --work-pool tvscreener
```

Validation (workers):
```bash
# Terminal 1 (worker)
uv run prefect worker start --pool tvscreener --type process --install-policy never

# Terminal 2 (trigger one-off runs)
uv run prefect deployment run "tvscreener-batch/opportunity-forex-majors-minors-data" --watch
uv run prefect deployment run "tvscreener-batch/opportunity-crypto-binance-majors-minors-data" --watch
uv run prefect deployment run "tvscreener-batch/opportunity-market-risk-proxy-data" --watch
```

Fast path (no watch):
```bash
uv run prefect deployment run "tvscreener-batch/opportunity-forex-majors-minors-data"
uv run prefect deployment run "tvscreener-batch/opportunity-crypto-binance-majors-minors-data"
uv run prefect deployment run "tvscreener-batch/opportunity-market-risk-proxy-data"
```

Runner-based scheduling (lightweight, recommended for single-machine):

Register deployments:
```bash
uv run python3 workflows/prefect/deploy_schedules.py --apply --engine runner
```

Start the runner (blocks; keep it running):
```bash
uv run python3 workflows/prefect/deploy_schedules.py --start-runner
```

To schedule `both` (data + analytics chained):
```bash
uv run python3 workflows/prefect/deploy_schedules.py --apply --mode both --engine worker --work-pool tvscreener
```

To schedule `analytics` rerenders (matrix-only, read-only with respect to signals tables):
```bash
uv run python3 workflows/prefect/deploy_schedules.py --apply --mode analytics --engine worker --work-pool tvscreener
```

Artifact publishing note:
- Analytics worker deployments set `job_variables.env.TVSCREENER_PUBLISH_TABLE_ARTIFACTS=1` so table artifacts are published alongside the Markdown artifact.
- They set `job_variables.env.TVSCREENER_PUBLISH_RESULTS_SUMMARY=1` to also publish the optional grade summary table.
- They set `job_variables.env.TVSCREENER_SEMANTIC_RUNTIME=sidemantic` by default for reproducibility (configurable via `.env` / `workflows/prefect/config.py`).

Lineage and health:
- The matrix Markdown artifact includes a `## Health` JSON block derived from the same Iceberg source table used for table artifacts.
- Health checks track duplicate/conflicting pairs and a ROC sanity check (`ROC_SCORE=0` while raw ROC_* are non-zero).
- Table artifacts are deduplicated to match the matrix (partition by `PAIR`, choose best row by confluence/score).

To create them paused first:
```bash
uv run python3 workflows/prefect/deploy_schedules.py --apply --paused --engine worker --work-pool tvscreener
```

### Operational notes

- Schedules are UTC by default.
- Data runs are rate-limited per worker (`min_interval_seconds` + jitter) and serialized (`data_concurrency=1`) to protect upstream.

Prefect API startup note:
- Immediately after `prefect server start`, the API may accept connections before it is ready; transient `503` can occur.
- Gate apply/run actions on the readiness endpoint:
  - `curl -sf http://127.0.0.1:4200/api/ready >/dev/null`

Prefect CSRF note:
- A `422` from `/api/csrf-token` indicates an invalid request shape (not necessarily an auth failure).
- If local CSRF support is noisy, disable client CSRF support via `PREFECT_CLIENT_CSRF_SUPPORT_ENABLED=false` (or enable server-side CSRF protection and use the full token flow).

### Validation (forex majors/minors data-only)

Trigger the deployment once:
```bash
uv run prefect deployment run "tvscreener-batch/opportunity-forex-majors-minors-data"
```

Expected artifacts:
- `artifacts/runs/batch/forex-majors-minors-data/batch_result.json`
- `artifacts/runs/<params_hash>/run_spec.json`
- `artifacts/runs/<params_hash>/run_result.json`

Expected lakehouse metadata:
```bash
uv run tvscreener-scan query tvscreener.runs --sql "SELECT asset_type, universe, pipeline_mode_executed, success, result_count, started_at_utc FROM df WHERE asset_type='forex' ORDER BY started_at_utc DESC LIMIT 6"
```

### Validation (crypto Binance majors/minors data-only)

Trigger the deployment once:
```bash
uv run prefect deployment run "tvscreener-batch/opportunity-crypto-binance-majors-minors-data"
```

Batch artifact:
- `artifacts/runs/batch/crypto-binance-majors-minors-data/batch_result.json`

Expected lakehouse metadata:
```bash
uv run tvscreener-scan query tvscreener.runs --sql "SELECT asset_type, universe, instrument_type, pipeline_mode_executed, success, result_count, started_at_utc FROM df WHERE asset_type='crypto' ORDER BY started_at_utc DESC LIMIT 8"
```

### Validation (market risk proxy data-only)

Trigger the deployment once:
```bash
uv run prefect deployment run "tvscreener-batch/opportunity-market-risk-proxy-data"
```

Batch artifact:
- `artifacts/runs/batch/market-risk-proxy-data/batch_result.json`

Expected lakehouse metadata:
```bash
uv run tvscreener-scan query tvscreener.runs --sql "SELECT asset_type, universe, pipeline_mode_executed, success, result_count, started_at_utc FROM df WHERE asset_type='stock' ORDER BY started_at_utc DESC LIMIT 8"
```
- Readiness check (no manual triggers):
  - Confirms Prefect API readiness and prints the next scheduled runs for the pool/queue:
    - `PREFECT_API_URL="http://127.0.0.1:4200/api" uv run python3 workflows/prefect/check_schedules.py --pool=tvscreener --work-queue=data,analytics --limit=10 --lookahead-minutes=90`

Worker queues (recommended split):
- Create two work queues in the `tvscreener` pool:
  - `data` (writers)
  - `analytics` (read-mostly)
- Apply deployments with queue routing:
  - `uv run python3 workflows/prefect/deploy_schedules.py --apply --mode data --engine worker --work-pool tvscreener --data-work-queue data`
  - `uv run python3 workflows/prefect/deploy_schedules.py --apply --mode analytics --engine worker --work-pool tvscreener --analytics-work-queue analytics`
- Start workers:
  - writer: `uv run prefect worker start --pool tvscreener --work-queue data --limit 1 --no-prompt`
  - reader: `uv run prefect worker start --pool tvscreener --work-queue analytics --limit 4 --no-prompt`
- Update the readiness checker to monitor both:
  - `PREFECT_API_URL="http://127.0.0.1:4200/api" uv run python3 workflows/prefect/check_schedules.py --pool=tvscreener --work-queue=data,analytics --limit=10 --lookahead-minutes=90`
  - Also reports:
    - work-queue paused state
    - last-seen timestamps for active workers
### Central Prefect config

To keep local/server/worker commands consistent, use the repo-local config and helper:
- Config defaults: `workflows/prefect/config.py`
- CLI helper: `workflows/prefect/prefectctl.py`
- Runbook: `workflows/prefect/README.md`

Config loading:
- `workflows/prefect/config.py` loads `.env` via `python-dotenv` and parses settings via `pydantic-settings`.

Prefect project config:
- `prefect.yaml` (generated by `prefect init`) is committed as the standard Prefect project config.

Settings split:
- Prefect-native project/deployment defaults live in `prefect.yaml` (work pool / default queue / job variables template).
- Runtime connection and repo-specific defaults live in `.env` and `workflows/prefect/config.py` (parsed via `pydantic-settings`).

Dotenv defaults:
- `TVSCREENER_PREFECT_HOST` and `TVSCREENER_PREFECT_PORT` are the source of truth for the local server bind address.

Deployment artifact defaults:
- `TVSCREENER_PREFECT_ANALYTICS_SEMANTIC_RUNTIME` controls the runtime forced into analytics/both deployments (`sidemantic` by default; use `auto` to omit).
- `TVSCREENER_PREFECT_ANALYTICS_PUBLISH_TABLE_ARTIFACTS` and `TVSCREENER_PREFECT_ANALYTICS_PUBLISH_RESULTS_SUMMARY` control Prefect artifact publication defaults.

Common commands:
```bash
# Server
uv run python3 workflows/prefect/prefectctl.py server start --background

# Workers
uv run python3 workflows/prefect/prefectctl.py worker --queue data --limit 1
uv run python3 workflows/prefect/prefectctl.py worker --queue analytics --limit 4

# Apply deployments (routes to queues)
uv run python3 workflows/prefect/prefectctl.py apply --mode data
uv run python3 workflows/prefect/prefectctl.py apply --mode analytics

# Readiness (no triggers)
uv run python3 workflows/prefect/prefectctl.py check --limit 10 --lookahead-minutes 90
```

Reproducibility notes:
- The runbook at `workflows/prefect/README.md` is the operator source of truth for bringing up a local server, work pool, queues, workers, and deployments.
- Re-applying deployments is expected and safe; it is how job env defaults for artifacts are refreshed.

Override defaults (optional):
- `TVSCREENER_PREFECT_HOST`, `TVSCREENER_PREFECT_PORT`
- `TVSCREENER_PREFECT_WORK_POOL`
- `TVSCREENER_PREFECT_DATA_QUEUE`, `TVSCREENER_PREFECT_ANALYTICS_QUEUE`
