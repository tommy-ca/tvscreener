## Design: Prefect scheduled batch runs

### What runs on a schedule

We schedule the `tvscreener-batch` Prefect flow (`workflows/prefect/run_batch.py`) with a `batch_path` parameter.

Default scheduling behavior: **data pipelines only**.

Analytics runs can be:
- invoked on demand (recommended), or
- scheduled as `pipeline_mode=both` to run analytics immediately after data.

### Strict persistence for scheduled data runs

Scheduled data runs enable strict persistence so Iceberg write failures fail the run instead of being swallowed.

This is implemented by setting `TVSCREENER_STRICT_PERSIST=1` for Prefect batch and single-run data tasks.

Strict persistence also applies to appending the audit row in `tvscreener.runs`.

### Analytics validation (post scheduled data)

After a scheduled data run completes, validate by rerendering the matrix from Iceberg:

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

Concurrency note:
- Iceberg writes use optimistic concurrency; concurrent runs can conflict ("branch main has changed").
- Prefer serial execution for writers: Prefect worker `--limit 1` and batch `data_concurrency=1`.

Example audit queries:
```bash
uv run tvscreener-scan query tvscreener.runs --sql "SELECT asset_type, universe, instrument_type, pipeline_mode_executed, success, result_count, started_at_utc FROM df WHERE pipeline_mode_executed='data' ORDER BY started_at_utc DESC LIMIT 12"

# Optional: verify a few key symbols are fresh in the analytics read-path.
uv run tvscreener-scan query tvscreener.signals_latest --sql "SELECT entity_id, strftime(fetched_at_utc,'%Y-%m-%d %H:%M:%S') AS fetched_at_utc, params_hash FROM df WHERE entity_id IN ('BINANCE:BTCUSDT','BINANCE:ETHUSDT') ORDER BY fetched_at_utc DESC LIMIT 10"
```

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
- When running under Prefect, matrix output is also published as a Prefect Markdown artifact (versioned by a stable key).
- Key format (approx): `tvscreener-matrix-<scanner>-<asset_type>-<instrument_type?>-<universe?>-<timeframe_set_id?>`.
- Key parts are sanitized (lowercase; non-`[a-z0-9-]` characters replaced with `-`).

Prefect UI tables:
- Analytics runs also publish a Prefect Table artifact with the top result rows.
- Key format mirrors the matrix key with `results` instead of `matrix`.
- The table is intended to explain the decision: price/liquidity context, grid + grade, and the component scores/dirs that drove the matrix.
- Current columns (when present): `PAIR`, `Name`, `Price`, `RVOL`, `Volume`, `ENSEMBLE_SCORE`, `GRADE`, `DIRECTION`, `GRID_ALIGNED`, `GRID_TOTAL`, `CONFLUENCE_LEVEL`, `TOTAL_CONFLUENCE`, `TF_CONFLUENCE`, `TREND_SCORE`, `MA_SCORE`, `OSC_SCORE`, `ROC_SCORE`, `ROC_AVG`, `TREND_DIR`, `MA_DIR`, `OSC_DIR`, `ROC_DIR`, `RATING_SCORE`.

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
  - forex majors: 2026-03-18 11:15:02
  - forex minors: 2026-03-18 11:17:28
  - crypto majors spot: 2026-03-18 11:25:13
  - crypto majors perp: 2026-03-18 11:27:29
  - crypto minors spot: 2026-03-18 11:29:38
  - crypto minors perp: 2026-03-18 11:31:56
  - market risk: 2026-03-18 11:45:07
- Analytics matrices rerendered from Iceberg at:
  - forex majors: 2026-03-18 11:40:04
  - forex minors: 2026-03-18 11:40:12
  - crypto majors spot: 2026-03-18 11:50:17
  - crypto majors perp: 2026-03-18 11:50:28
  - crypto minors spot: 2026-03-18 11:48:17
  - crypto minors perp: 2026-03-18 11:48:26
  - market risk: 2026-03-18 11:49:18

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
