## Design: Prefect scheduled batch runs

### What runs on a schedule

We schedule the `tvscreener-batch` Prefect flow (`workflows/prefect/run_batch.py`) with a `batch_path` parameter.

Default scheduling behavior: **data pipelines only**.

Analytics runs can be:
- invoked on demand (recommended), or
- scheduled as `pipeline_mode=both` to run analytics immediately after data.

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

3) Start a worker:
```bash
uv run prefect worker start --pool tvscreener
```

4) Register deployments (cron schedules):
```bash
uv run python workflows/prefect/deploy_schedules.py --apply --work-pool tvscreener
```

Runner-based scheduling (lightweight, recommended for single-machine):

Register deployments:
```bash
uv run python workflows/prefect/deploy_schedules.py --apply
```

Start the runner (blocks; keep it running):
```bash
uv run python workflows/prefect/deploy_schedules.py --start-runner
```

To schedule `both` (data + analytics chained):
```bash
uv run python workflows/prefect/deploy_schedules.py --apply --mode both --work-pool tvscreener
```

To create them paused first:
```bash
uv run python workflows/prefect/deploy_schedules.py --apply --paused --work-pool tvscreener
```

### Operational notes

- Schedules are UTC by default.
- Data runs are rate-limited per worker (`min_interval_seconds` + jitter) and serialized (`data_concurrency=1`) to protect upstream.
