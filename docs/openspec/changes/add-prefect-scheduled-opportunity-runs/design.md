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
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe majors --timeframes 240,60,15 --pipeline analytics --matrix
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe minors --timeframes 240,60,15 --pipeline analytics --matrix

PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline analytics --matrix
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline analytics --matrix
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline analytics --matrix
PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --pipeline analytics --matrix

PREFECT_HOME="$PWD/.prefect-home" PREFECT_API_URL="http://127.0.0.1:4200/api" \
  uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type stock --universe market_risk --timeframes 240,60,15 --pipeline analytics --matrix
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

`params_hash` note:
- `params_hash` is derived from a normalized `PipelineRunSpec`.
- Ordering of list fields matters (e.g. `timeframes`); keep `timeframes` in a stable order (recommended: `15,60,240`) to keep `params_hash` stable across reruns.

Latest validated matrices:
- `artifacts/runs/e4d3e44e6fa50fb549ccb3645a5c76cf25f8915de48e79f9f3b3d6816c482422/matrix.txt` (forex majors)
- `artifacts/runs/fb64d6d11b583d906aab257e02052d15fdd909547547d905386dfcc216e09c1a/matrix.txt` (forex minors)
- `artifacts/runs/5d39896c7b206a5732d787e4ac613b4facb7ded55922302ae30e7f0a701d1e13/matrix.txt` (crypto spot majors)
- `artifacts/runs/534a87f6f0598cc24fe08667623ec8ba12b05ce8043df9bc1a2a69abeb3df0e0/matrix.txt` (crypto perp majors)
- `artifacts/runs/7a0d1f3ea396d92df61dca07def1079bf09c56981b80be698168383953036a57/matrix.txt` (crypto spot minors)
- `artifacts/runs/29b3377f46f41db36d308398229075cce176b49b45b8f7bff5c9ad7deabb20ee/matrix.txt` (crypto perp minors)
- `artifacts/runs/ad9fe17e402518d372066373b2f451b39cefd6c74c4c509b09e3027c1ca163a3/matrix.txt` (market risk)

Validated at (UTC):
- Data freshness validated via `tvscreener.runs`; latest `pipeline_mode_executed='data'` start times:
  - forex majors: 2026-03-17 17:15:03
  - forex minors: 2026-03-17 17:16:36
  - crypto majors spot: 2026-03-17 17:25:08
  - crypto majors perp: 2026-03-17 17:26:42
  - crypto minors spot: 2026-03-17 17:28:10
  - crypto minors perp: 2026-03-17 17:29:49
  - market risk: 2026-03-17 17:31:43
- Analytics matrices rerendered from Iceberg at:
  - forex majors: 2026-03-17 17:43:29
  - forex minors: 2026-03-17 17:43:48
  - crypto majors spot: 2026-03-17 17:44:08
  - crypto majors perp: 2026-03-17 17:44:28
  - crypto minors spot: 2026-03-17 17:44:48
  - crypto minors perp: 2026-03-17 17:45:10
  - market risk: 2026-03-17 17:45:30

Validation note:
- Verified scheduled `data` runs were recent (within the last hour) before rerendering the analytics matrices.
- Verified analytics rerenders wrote `matrix.txt` and appended `pipeline_mode_executed='analytics'` rows to `tvscreener.runs`.

Batch specs:
- `workflows/prefect/batches/forex_majors_minors_both.json` (existing)
- `workflows/prefect/batches/forex_majors_minors_data.json`
- `workflows/prefect/batches/crypto_binance_majors_minors_both.json`
- `workflows/prefect/batches/crypto_binance_majors_minors_data.json`
- `workflows/prefect/batches/market_risk_proxy_both.json`
- `workflows/prefect/batches/market_risk_proxy_data.json`

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
