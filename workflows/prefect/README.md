## Prefect wrapper (uv-only)

This directory contains an **optional** Prefect wrapper that runs `tvscreener` pipeline runs defined by a
`PipelineRunSpec` JSON payload.

### Install (optional)

```bash
uv sync --extra prefect
```

### Runtime notes (uv-managed, no global Python)

- This repo is intended to run under `uv` with an **uv-managed Python**.
- If Prefect’s temporary server is slow to start on first run (migrations), increase the startup timeout:

```bash
PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180 \
uv run --extra prefect python workflows/prefect/run_batch.py --help
```

### Export a spec (engine-agnostic)

```bash
uv run tvscreener-scan --runner export --scanner opportunity --pipeline both --asset-type forex --universe majors > run_spec.json
```

### Execute with Prefect locally

```bash
uv run --extra prefect python workflows/prefect/run_flow.py --spec run_spec.json
```

### Path semantics (important for reruns)

- `python workflows/prefect/run_flow.py` and `python workflows/prefect/run_batch.py` run with the **repo root** as
  the working directory, so a relative `--artifacts-dir` (default `artifacts/prefect`) is stable across reruns.
- `tvscreener-scan --runner prefect` runs inside the current process and resolves a relative `--artifacts-dir`
  from the **invocation working directory**.
  - Recommendation: run the seamless CLI form from the repo root, or pass an absolute `--artifacts-dir`.

### Seamless CLI runner (no intermediate spec file)

```bash
uv run --extra prefect tvscreener-scan --runner prefect --scanner opportunity --pipeline both --asset-type forex --universe majors --timeframes 15,60,240 --config tvscreener.yaml
```

### Artifacts (analytics workflows)

Artifacts are written under `artifacts/prefect/<params_hash>/` by default (or `--artifacts-dir`).

- **Always**:
  - `run_spec.json`
- **Result JSON**:
  - `run_result_analytics.json` for `--pipeline analytics`
  - `run_result.json` for `--pipeline both` (includes `analytics.results_path`)
- **Analytics output file**:
  - if `--output` is omitted, defaults to `<scanner_family>_results.parquet` under the run directory
  - the emitted path is recorded as `results_path` in the result JSON

### Execute a batch (fan-out) locally

Batch JSON can be either:
- a JSON list of `PipelineRunSpec` objects, or
- an object with `defaults` + `runs` and/or a `matrix` expansion.

Example batch file:

```json
{
  "batch_id": "mtf-forex-smoke",
  "defaults": { "asset_type": "forex", "timeframes": ["15", "60", "240"] },
  "sharding": { "enabled": true, "max_pairs_per_run": 10 },
  "matrix": {
    "scanners": ["opportunity", "strategy"],
    "universes": ["majors", "minors"],
    "pipeline_mode": "analytics"
  }
}
```

Run it:

```bash
uv run --extra prefect python workflows/prefect/run_batch.py --batch batch.json --concurrency 4
```

#### Idempotent reruns (skip existing artifacts)

To make reruns cheaper and faster, you can skip stages that already have result artifacts:

```bash
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch batch.json \
  --skip-existing
```

### Forex majors/minors rerun runbook (data + analytics)

The repo includes ready-to-run batch specs under `workflows/prefect/batches/`:

- **Full refresh (data then analytics)**: `workflows/prefect/batches/forex_majors_minors_both.json`
- **Analytics-only replay**: `workflows/prefect/batches/forex_majors_minors_analytics.json`

Run a full refresh safely (recommended defaults for upstream protection):

```bash
uv sync --extra prefect
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch workflows/prefect/batches/forex_majors_minors_both.json \
  --data-concurrency 1 \
  --analytics-concurrency 8 \
  --rate-limit-min-interval 1.0 \
  --rate-limit-jitter 0.25
```

Replay analytics-only quickly (no upstream calls):

```bash
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch workflows/prefect/batches/forex_majors_minors_analytics.json \
  --concurrency 12
```

#### Rerun semantics (what changes on disk vs in Iceberg)

- **Data runs** (`pipeline_mode=data|both`) will update Iceberg tables for the selected universe/timeframe set.
- **Analytics runs** (`pipeline_mode=analytics|both`) are expected to be **read-only w.r.t. Iceberg** and only emit
  artifacts (result parquet + result JSON) under `artifacts/prefect/<params_hash>/`.
- Re-running the same batch will re-use the same `params_hash` directories, so outputs are deterministic; expect
  existing artifact files to be overwritten.

#### Rate limiting + split concurrency (recommended for data runs)

For runs that include `pipeline_mode=data` or `both`, protect upstream fetch with:
- lower data concurrency
- a per-worker minimum interval between starting data tasks

```bash
uv run --extra prefect python workflows/prefect/run_batch.py --batch batch.json \
  --data-concurrency 1 \
  --analytics-concurrency 8 \
  --rate-limit-min-interval 1.0 \
  --rate-limit-jitter 0.25
```

### Forex all-universe rerun runbook (matrix view)

All-universe refresh is heavier than majors/minors. The repo includes two batch specs:

- **Full refresh (recommended)**: `workflows/prefect/batches/forex_all_refresh.json`
  - runs **opportunity** as `both` (data + analytics matrix)
  - runs **strategy** as `analytics` only (avoids duplicating upstream fetch; strategy analytics reads `signals_latest`)
- **Analytics-only replay**: `workflows/prefect/batches/forex_all_analytics.json`

Run a full refresh safely:

```bash
export PREFECT_HOME="$PWD/.prefect-home"
export PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180
uv sync --extra prefect
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch workflows/prefect/batches/forex_all_refresh.json \
  --data-concurrency 1 \
  --analytics-concurrency 8 \
  --rate-limit-min-interval 1.0 \
  --rate-limit-jitter 0.25 \
  --skip-existing
```

Replay analytics-only:

```bash
export PREFECT_HOME="$PWD/.prefect-home"
export PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=180
uv run --extra prefect python workflows/prefect/run_batch.py \
  --batch workflows/prefect/batches/forex_all_analytics.json \
  --concurrency 12 \
  --skip-existing
```

