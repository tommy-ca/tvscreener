## Plan

### Goal
Make TradingView `/scan` batching reliable by ensuring that when we send an explicit `symbols.tickers` list, the
request `range` covers the full list so responses are not silently truncated at 150 rows.

### Steps
- Update requirements/specs to capture the rule and scenarios.
- Implement client behavior:
  - detect when range is still default
  - if tickers are provided, set payload range to `[0, len(tickers)]`
- Add a regression test that fails if the outgoing payload still uses `[0,150]` with a large tickers list.

### Acceptance criteria
- Batched tickers requests (>150) return all requested symbols (subject to availability).
- No behavior change for `symbols.query` scans that rely on paging via `range`.
- Unit tests validate payload semantics without needing network calls.

### Rerun / validation plan (data + analytics)

#### A) Fast local probe (no Iceberg writes)
Run a direct `/scan` request with an explicit tickers list >150 and ensure `len(df) == len(tickers)`:

```bash
uv run python - <<'PY'
from tvscreener.core.forex import ForexScreener
from tvscreener.constants.forex import DEFAULT_FOREX_PAIRS, LIQUID_EXCHANGES

pairs = list(DEFAULT_FOREX_PAIRS)
exs = list(LIQUID_EXCHANGES)
tickers = [f"{ex}:{p}" for ex in exs for p in pairs]
print("tickers", len(tickers))

ss = ForexScreener()
ss.set_tickers(*tickers)
df = ss.get()
print("returned_rows", len(df))
PY
```

#### B) Data pipeline rerun (Iceberg updated)
Run a scanner run that necessarily batches >150 tickers (forex `--universe all`):

```bash
uv run tvscreener-scan --scanner opportunity --pipeline data --asset-type forex --universe all --timeframes 15,60,240 --config tvscreener.yaml
```

#### C) Analytics rerun (read-only) with artifacts
Run analytics-only from Iceberg and export results to an artifact:

```bash
uv run tvscreener-scan --scanner opportunity --pipeline analytics --asset-type forex --universe all --timeframes 15,60,240 --config tvscreener.yaml --output artifacts/validation/opportunity_all.parquet
```

Or via Prefect wrapper (always writes artifacts):

```bash
uv run tvscreener-scan --runner export --spec-out /tmp/spec_opportunity_all_analytics.json \
  --scanner opportunity --pipeline analytics --asset-type forex --universe all --timeframes 15,60,240 --config tvscreener.yaml
uv run --extra prefect python workflows/prefect/run_flow.py --spec /tmp/spec_opportunity_all_analytics.json
```

#### D) Prefect batch rerun (scale baseline)
Run a batch that shards a universe into `pairs` chunks and runs `both` with rate limiting:

```bash
uv run python -c "import json, pathlib; pathlib.Path('/tmp/batch.json').write_text(json.dumps({\
  'batch_id':'tvscan-range-verify',\
  'defaults':{'asset_type':'forex','timeframes':['15','60','240'],'pipeline_mode':'both'},\
  'sharding':{'enabled':True,'max_pairs_per_run':10},\
  'matrix':{'scanners':['opportunity'],'universes':['all'],'pipeline_mode':'both'}\
}, indent=2), encoding='utf-8')"

uv run --extra prefect python workflows/prefect/run_batch.py --batch /tmp/batch.json \
  --data-concurrency 1 \
  --analytics-concurrency 4 \
  --rate-limit-min-interval 0.5 \
  --rate-limit-jitter 0.1
```

Validation:
- `artifacts/runs/batch/tvscan-range-verify/batch_result.json` exists
- each `artifacts/runs/<params_hash>/opportunity_results.parquet` exists and has a non-zero row count
