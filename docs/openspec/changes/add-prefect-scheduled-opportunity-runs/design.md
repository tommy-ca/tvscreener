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

Recommended operator policy:
- Treat data as "fresh" when the latest successful `pipeline_mode_executed='data'` run is within the last 60 minutes.
- If stale, trigger the `*-data` deployments via a Prefect worker, then rerender analytics.

Example audit queries:
```bash
uv run tvscreener-scan query tvscreener.runs --sql "SELECT asset_type, universe, instrument_type, pipeline_mode_executed, success, result_count, started_at_utc FROM df WHERE pipeline_mode_executed='data' ORDER BY started_at_utc DESC LIMIT 12"

# Optional: verify a few key symbols are fresh in the analytics read-path.
uv run tvscreener-scan query tvscreener.signals_latest --sql "SELECT entity_id, strftime(fetched_at_utc,'%Y-%m-%d %H:%M:%S') AS fetched_at_utc, params_hash FROM df WHERE entity_id IN ('BINANCE:BTCUSDT','BINANCE:ETHUSDT') ORDER BY fetched_at_utc DESC LIMIT 10"
```

Latest validated matrices:
- `artifacts/runs/70696cd35fb6f9f781e621a79fe0df995e70adb6925ed81052ba9aaad8fcc890/matrix.txt` (forex majors)
- `artifacts/runs/2ed6f942ae981b9c26606953e7a5a679efc1ed5526bbae63953cebc35517393f/matrix.txt` (forex minors)
- `artifacts/runs/b966754797cb6428bfe242b903c82119bcd923224be60299f8c3c8c6883d1e8e/matrix.txt` (crypto spot majors)
- `artifacts/runs/02cdbd5ea6d54772f41e63878f3ece1df983038d485d12daf1d44212a99d984b/matrix.txt` (crypto perp majors)
- `artifacts/runs/3f18bd080d54f2118eeee02be0f79f9eab605cfe95d8977de244d7051a577388/matrix.txt` (crypto spot minors)
- `artifacts/runs/6b1f70993b3d2628e7f67014a74e41b1d6073ebc1c038fd18153e89bee97d5ed/matrix.txt` (crypto perp minors)
- `artifacts/runs/504ad7c6595b6e54d95243e9919d623e0bc7503acb42151fa5eab432c28dbaf1/matrix.txt` (market risk)

Validated at (UTC):
- Data freshness refreshed via Prefect worker; latest `pipeline_mode_executed='data'` start times:
  - forex majors: 2026-03-16 12:18:00
  - forex minors: 2026-03-16 12:19:05
  - crypto majors spot: 2026-03-16 12:27:22
  - crypto majors perp: 2026-03-16 12:28:33
  - crypto minors spot: 2026-03-16 12:29:44
  - crypto minors perp: 2026-03-16 12:30:58
  - market risk: 2026-03-16 12:45:05
- Analytics matrices rerendered from Iceberg at:
  - forex majors: 2026-03-16 12:53:55
  - forex minors: 2026-03-16 12:53:58
  - crypto majors spot: 2026-03-16 12:54:32
  - crypto majors perp: 2026-03-16 12:54:35
  - crypto minors spot: 2026-03-16 12:55:15
  - market risk: 2026-03-16 12:55:51

Validation note:
- Verified scheduled `data` runs were recent (within the last hour) before rerendering the analytics matrices.

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
