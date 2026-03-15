# Plan: Forex all-universe matrix rerun + docs refresh

date: 2026-03-07
branch: feat/forex-strategy-scanner

## Goals
- Rerun **data** pipelines for forex `all` universe.
- Rerun **analytics** pipelines to produce the **matrix view** for forex screeners.
- Update requirements/specs/design docs based on what the rerun reveals.
- Run against a dedicated Prefect server (non-ephemeral) for parity.
- Make `.env` + config defaults minimize required CLI flags.

## Scope
- Forex asset type.
- Universe: `all`.
- Screeners/scanners: `opportunity` (data + analytics), `strategy` (analytics).

## Checklist
- [x] Review current requirements/specs/design docs for pipeline + matrix view
- [x] Rerun data pipeline (forex/all)
- [x] Rerun analytics pipeline (forex/all) and capture matrix output
- [x] Update requirements/specs/design docs with findings
- [x] Record final commands + outcomes here
- [x] Audit current artifacts architecture
- [x] Propose minimal artifacts contract and migration plan
- [x] Implement write-side v2 artifacts (runs base + single result JSON)

## Commands

### Prefect server (local parity)
```bash
export PREFECT_HOME="$PWD/.prefect-home"
prefect server start --host 127.0.0.1 --port 4200
export PREFECT_API_URL="http://127.0.0.1:4200/api"
```

With `.env` configured (see `.env.example`), you can omit the explicit exports.

### Data
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline data --asset-type forex --universe all --config tvscreener.yaml
```

### Analytics (matrix)
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline analytics --asset-type forex --universe all --matrix --limit 100 --config tvscreener.yaml
uv run tvscreener-scan --runner prefect --scanner strategy --pipeline analytics --asset-type forex --universe all --matrix --limit 100 --config tvscreener.yaml
```

## Results
- Prefect ephemeral server initially failed with `Can't locate revision identified by ...` due to a stale local DB.
  - Fix: `mv .prefect-home .prefect-home.bak-20260307-2023 && mkdir .prefect-home`
- Started a dedicated Prefect server (`prefect server start --background`) and ran all pipelines against it via `PREFECT_API_URL`.
- Updated defaults so the parity workflow needs fewer flags:
  - `.env.example` includes `PREFECT_API_URL` and sets `TVSCREENER_DEFAULT_UNIVERSE=all`
  - `tvscreener.yaml` and `ScreenerSettings.default_universe` default to `all`
  - CLI best-effort loads `.env` into `os.environ`
- Added local `.env` (gitignored) and documented `cp .env.example .env`.

- Reran forex `all` via a dedicated Prefect server (`PREFECT_API_URL=http://127.0.0.1:4200/api`) using artifacts v2 (`artifacts/runs/`).
  - Data: `artifacts/matrix/forex_all_data_prefect_server_v2.log`
    - Artifacts: `artifacts/runs/d49faa9dd9e0e9cd913958a617040f5c0eeb56c6c775fafec55f53d97bd09383/run_result.json`
  - Opportunity analytics (matrix): `artifacts/matrix/forex_all_opportunity_analytics_prefect_server_v2.log`
    - Artifacts: `artifacts/runs/4dee96c25388f26a512b785ccc7388c58f73388b5446704f332e5d483b7428d5/run_result.json`
    - Matrix: `artifacts/runs/4dee96c25388f26a512b785ccc7388c58f73388b5446704f332e5d483b7428d5/matrix.txt`
  - Strategy analytics (matrix): `artifacts/matrix/forex_all_strategy_analytics_prefect_server_v2.log`
    - Artifacts: `artifacts/runs/2609f3a93d1ecdceab2312c110626d48d9d8d576e39e2da1753578377365135d/run_result.json`
    - Matrix: `artifacts/runs/2609f3a93d1ecdceab2312c110626d48d9d8d576e39e2da1753578377365135d/matrix.txt`

- Reran forex `all` again on 2026-03-09 (Prefect server parity):
  - Data log: `artifacts/matrix/forex_all_data_prefect_server_2026-03-09.log`
  - Opportunity analytics log: `artifacts/matrix/forex_all_opportunity_analytics_prefect_server_2026-03-09.log`
    - Matrix: `artifacts/runs/4dee96c25388f26a512b785ccc7388c58f73388b5446704f332e5d483b7428d5/matrix.txt`
  - Strategy analytics log: `artifacts/matrix/forex_all_strategy_analytics_prefect_server_2026-03-09.log`
    - Matrix: `artifacts/runs/2609f3a93d1ecdceab2312c110626d48d9d8d576e39e2da1753578377365135d/matrix.txt`

## Artifacts audit (current)

Current observed directories:
- `artifacts/runs/<params_hash>/`: canonical run artifacts (`run_spec.json`, `run_result.json`, parquet, optional `matrix.txt`).
- `artifacts/runs/batch/<batch_id>/`: batch result summary.
- `artifacts/prefect/<params_hash>/`: legacy run artifacts from older defaults.
- `artifacts/prefect/batch/<batch_id>/`: legacy batch summaries.
- `artifacts/matrix/`: ad-hoc operator log captures (not a stable contract).
- `artifacts/validation/`: ad-hoc validation outputs.

Issues to address:
- Multiple result JSON variants (`run_result_data.json`, `run_result_analytics.json`, `run_result.json`) complicate consumers.
- Base dir name is engine-prefixed (`prefect`) even though `PipelineRunSpec` is engine-agnostic.
- Non-run files can accumulate at the base dir (e.g. top-level `.parquet`).

Planned direction:
- Introduce an engine-agnostic minimal artifacts contract under `artifacts/runs/<params_hash>/` with exactly one `run_result.json`.
- Keep `matrix.txt` optional (only when `matrix=true`).
- Keep batch summary to a single `batch_result.json`.

## Essential artifacts (target)

Per run (`artifacts/runs/<params_hash>/`):
- `run_spec.json` (normalized `PipelineRunSpec`; stable inputs)
- `run_result.json` (single, self-describing outcome payload)
- `<scanner_family>_results.parquet` (analytics outputs; required when analytics succeeds)
- `matrix.txt` (only when `matrix=true`)

Per batch (`artifacts/runs/batch/<batch_id>/`):
- `batch_result.json` (batch summary + per-run pointers)

Everything else is explicitly non-contract:
- ad-hoc console log captures (prefer `logs/` or `artifacts/debug/`, not the contract base)
- one-off validation snapshots (prefer `artifacts/validation/` but treat as operator-owned)

## Cleanup plan (phased)

1) Contract v2 (write-side)
- Add a canonical base dir `artifacts/runs/` (engine-agnostic)
- Keep `artifacts/prefect/` as a legacy alias during transition
- Ensure all modes write exactly one `run_result.json`

2) Migration tooling
- Add `tvscreener-scan maintenance` subcommand to migrate/prune:
  - move `artifacts/prefect/<params_hash>/` -> `artifacts/runs/<params_hash>/`
  - remove deprecated stage JSONs when `run_result.json` exists
  - flag unexpected top-level files under base dirs

3) Deprecation
- Update docs/runbooks to reference `artifacts/runs/`
- Remove stage-specific JSON writes in a later release window

## Next: Binance crypto (spot + perps) scan plan

Goal: scan Binance crypto markets (spot + perps) using the shared opportunity scanner.

Constraints:
- rank: top 100 by 24h quote volume (USD)
- filters: quote volume >= 10,000,000 and 24h volatility >= 3%

Planned work (spec-driven):
- Add OpenSpec change: `docs/openspec/changes/add-binance-crypto-opportunity-scan/`
- Use TradingView crypto `/scan` filtered to `Exchange=BINANCE` and `Type in {spot, swap}`
- Implement deterministic universe selector (top 100 by `Volume 24h in USD`, min volume, min volatility)
- Persist `universe.json` under `artifacts/runs/<params_hash>/` for reproducibility
- Add Prefect batch template(s) for crypto spot/perps

Build status:
- Implemented TradingView-driven Binance crypto universe selection in orchestrator:
  - `--asset-type crypto --universe binance_spot_top100`
  - `--asset-type crypto --universe binance_perp_top100`
- Added `instrument_type` to the run spec + CLI (`--instrument-type spot|perp`) and propagates to `TVSCREENER_INSTRUMENT_TYPE`.
- Added Prefect batch templates:
  - `workflows/prefect/batches/crypto_binance_spot_top100_both.json`
  - `workflows/prefect/batches/crypto_binance_perp_top100_both.json`

## Review plan: crypto opportunity pipelines

Goal: review the current crypto opportunity data + analytics pipelines (spot + perps) for correctness, determinism, and table isolation.

Checklist:
- Data pipeline (Bronze->Silver->Gold)
  - Verify selected columns exist for crypto (volume, volatility/ATR, RECOMMEND*, ROC*)
  - Verify `entity_id` and `instrument_type` are present and correct in Silver/Gold
  - Verify scalable layout writes to isolated tables when `TVSCREENER_LAKEHOUSE_LAYOUT=scalable`
- Analytics pipeline
  - Verify reads `signals_latest` from the correct product table id (layout-aware)
  - Verify matrix rendering works for crypto spot and perp
- Universe determinism
  - Universe selector runs once per Prefect flow, writes `universe.json`, and freezes `pairs` into `run_spec.json`

Suggested commands (small smoke before top100):
```bash
PREFECT_API_URL=http://127.0.0.1:4200/api uv run tvscreener-scan \
  --runner prefect --scanner opportunity --pipeline both --asset-type crypto \
  --pairs BINANCE:BTCUSDT BINANCE:BTCUSDT.P --timeframes 15,60,240 --matrix --limit 50
```

## Next build: crypto market cap top100 (spot + perps)

Universes:
- `binance_spot_mcap_top100`
- `binance_perp_mcap_top100`

Selection:
- take top 100 coins by market cap (TradingView coin `/scan` `Market Cap Calc`)
- map to Binance `USDT` markets (spot or perp)
- emit the raw universe (no filters)
- filter/sort later with DuckDB analytics queries (volume + volatility)

Artifacts:
- `universe.json` includes the market-cap-derived base list (`market_cap_bases`) and per-market rows (`entity_id`, `symbol`, `quote_volume_usd`, `volatility_24h_pct`).

## Results: Binance mcap top100 universes

Built and wrote universe snapshots (market cap top100 -> map to Binance tickers; no filters applied):
- spot: `artifacts/runs/a5dd40eb07523521a0313dbcce59f387527382c57da57844debd5f4c63c522ea/universe.json` (count=38, missing=62)
- perp: `artifacts/runs/2e7987cd48b99786c87773582b6a04b68bc23f928f06d3b96dceaf12dbe6b295/universe.json` (count=33, missing=67)

## Next: CS momentum candidate universes

Goal: build Binance spot/perp universes tuned for cross-sectional momentum trading (before ROC/momentum ranking).

Universes:
- `binance_spot_cs_momentum`
- `binance_perp_cs_momentum`

Idea: seed from market cap top 200, exclude stable/wrapped bases, apply only liquidity eligibility gate, then rank by USD trading value.
OpenSpec: `docs/openspec/changes/add-binance-cs-momentum-universe/`

## Review plan: Binance crypto universes

Current universes (spot + perp variants):
- `binance_{spot,perp}_top100`: TradingView crypto /scan rank by `Volume 24h in USD`, selection-time filters (min volume + min volatility).
- `binance_{spot,perp}_mcap_top100`: TradingView coin /scan market-cap seed -> map to Binance tickers; no filters at selection time.
- `binance_{spot,perp}_cs_momentum`: market-cap seed -> exclude stables/wrapped -> liquidity gate; ordered by USD trading value.

New base universes (tradeable-first):
- `binance_{spot,perp}_tradeable_base`: Binance-first, liquid, USDT/USDC-quoted, stable/wrapped bases excluded.

Defaults (tuned for parity):
- spot min volume: `2_500_000`
- perp min volume: `20_000_000`

Base-universe recommendation:
- Use `binance_{spot,perp}_tradeable_base` as the default **base universe** for strategy research (tradeable-first).
- Keep `binance_{spot,perp}_mcap_top100` as a reference universe for market-cap coverage audits.
- Derive strategy-specific candidates from the base:
  - momentum: `binance_{spot,perp}_cs_momentum` (eligibility gate only)
  - short-term opportunity: `binance_{spot,perp}_top100` (selection-time gates)

Audit checklist for each universe:
- Determinism: `universe.json` written, includes `requested_tickers` and `missing_tickers`.
- Instrument isolation: `instrument_type` is correct (`spot` vs `perp`).
- Eligibility vs ranking: selection-time filtering kept minimal for “base” universes.

Audit snapshot (current):
- `binance_spot_top100`: 100
- `binance_perp_top100`: 100
- `binance_spot_mcap_top100`: 39
- `binance_perp_mcap_top100`: 34
- `binance_spot_cs_momentum`: 52
- `binance_perp_cs_momentum`: 52
- `binance_spot_tradeable_base`: 100
- `binance_perp_tradeable_base`: 103
- `binance_spot_tradeable_mcap_cs`: 31
- `binance_perp_tradeable_mcap_cs`: 27

Audit artifacts:
- `artifacts/audits/binance-universes/report.json`

Audit command:
```bash
uv run tvscreener-scan audit binance-universes --out-dir artifacts/audits/binance-universes
```

DuckDB report command:
```bash
uv run tvscreener-scan report binance-universes --in-dir artifacts/audits/binance-universes --out-dir artifacts/reports/binance-universes
```

One-shot review command:
```bash
uv run tvscreener-scan review binance-universes --audit-out-dir artifacts/audits/binance-universes --report-out-dir artifacts/reports/binance-universes
```

Strict mode:
```bash
uv run tvscreener-scan review binance-universes --strict
```

Extended diagnostics:
```bash
uv run tvscreener-scan review binance-universes --include-all
```

Universe aliases (ergonomic CLI names):
- `binance_spot_base` / `binance_perp_base` -> tradeable base universes
- `binance_spot_largecap` / `binance_perp_largecap` -> tradeable market-cap cross-section
- `binance_spot_snapshot` / `binance_perp_snapshot` -> top100 volume snapshot

Majors/minors universes:
- `binance_{spot,perp}_majors`: mcap ranks 1..20 intersect tradeable gates
- `binance_{spot,perp}_minors`: mcap ranks 21..200 intersect tradeable gates

Forex-style usage for crypto:
- `--universe majors|minors` maps to crypto majors/minors when `asset_type=crypto` and `--instrument-type spot|perp` is set.

Recommended scanner defaults:
- Opportunity scanner: `--universe majors` (add `minors` for breadth)
- Strategy research: `binance_{spot,perp}_tradeable_base` (TS) and `binance_{spot,perp}_tradeable_mcap_cs` (CS)

Crypto opportunity scanner presets:
- Spot majors: `uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline both`
- Perp majors: `uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline both`

Validation run outputs (local runner):
- `artifacts/validation/opportunity_crypto_spot_majors_both.parquet`
- `artifacts/validation/opportunity_crypto_spot_majors_analytics.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_both.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_analytics.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_both.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_both.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_analytics.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_analytics.parquet`

Matrix view validation outputs:
- `artifacts/validation/opportunity_crypto_spot_majors_matrix.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_matrix.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_matrix.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_matrix.parquet`

Matrix view after Iceberg publish:
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_after_iceberg.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_matrix_after_iceberg.parquet`

Matrix view after Iceberg persistence fix:
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_after_persist_fix.parquet`

Matrix view after minors data publish:
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_post_minors_publish.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_matrix_post_minors_publish.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_matrix_post_publish.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_matrix_post_publish.parquet`

Matrix view after TDD rerun (data+analytics):
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_tdd.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_matrix_tdd.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_matrix_tdd.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_matrix_tdd.parquet`

Latest matrix view outputs (analytics-only):
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_final.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_matrix_final.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_matrix_final.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_matrix_final.parquet`

Matrix view outputs (after `entity_id` analytics fix):
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_after_entityid_fix.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_matrix_after_entityid_fix.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_matrix_after_entityid_fix.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_matrix_after_entityid_fix.parquet`

Matrix view readability:
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_pairfix2.parquet` (PAIR filled from symbol)

Forex parity matrix outputs:
- `artifacts/validation/opportunity_forex_majors_matrix_parity.parquet`
- `artifacts/validation/opportunity_forex_minors_matrix_parity.parquet`

Forex full-loop (data then analytics) outputs:
- `artifacts/validation/opportunity_forex_majors_data.parquet`
- `artifacts/validation/opportunity_forex_minors_data.parquet`
- `artifacts/validation/opportunity_forex_majors_matrix_data_analytics.parquet`
- `artifacts/validation/opportunity_forex_minors_matrix_data_analytics.parquet`

Recent full-loop outputs (data then analytics):
- `artifacts/validation/opportunity_forex_majors_data_recent.parquet`
- `artifacts/validation/opportunity_forex_minors_data_recent.parquet`
- `artifacts/validation/opportunity_forex_majors_matrix_recent.parquet`
- `artifacts/validation/opportunity_forex_minors_matrix_recent.parquet`
- `artifacts/validation/opportunity_crypto_spot_majors_data_recent.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_data_recent.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_data_recent.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_data_recent.parquet`
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_recent.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_matrix_recent.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_matrix_recent.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_matrix_recent.parquet`

Crypto parity matrix outputs:
- `artifacts/validation/opportunity_crypto_spot_majors_matrix_parity.parquet`
- `artifacts/validation/opportunity_crypto_perp_majors_matrix_parity.parquet`
- `artifacts/validation/opportunity_crypto_spot_minors_matrix_parity.parquet`
- `artifacts/validation/opportunity_crypto_perp_minors_matrix_parity.parquet`

Matrix renderer parity:
- Crypto opportunity screeners now render the same Confluence Matrix format as forex (not the generic table).
- Crypto `PAIR` labels are venue-stripped (e.g. `BINANCE:BTCUSDT` -> `BTCUSDT`) for spot/perp majors/minors.

Note: run spot/perp `--pipeline data` sequentially in local/dev when using shared Iceberg tables.

Latest screeners-only review report:
- `artifacts/reports/binance-universes/20260313-004142/report.md`

Latest strict review report:
- `artifacts/reports/binance-universes/20260313-153326/report.md`

Latest strict review report (post majors/minors rerun):
- `artifacts/reports/binance-universes/20260313-160901/report.md`

Latest strict review report (post Prefect parity rerun):
- `artifacts/reports/binance-universes/20260313-163456/report.md`

Latest strict review report (post forex+crypto full rerun):
- `artifacts/reports/binance-universes/20260313-173851/report.md`

Latest strict review report (post forex+crypto full rerun, 2026-03-14):
- `artifacts/reports/binance-universes/20260314-115838/report.md`

Latest strict review report (post forex+crypto full rerun, 2026-03-15):
- `artifacts/reports/binance-universes/20260315-022540/report.md`

Latest full rerun matrices (Prefect, analytics):
- `artifacts/runs/5411af003b204811aae87b4e901142019fd714d3146a7ae7c06b860b9497f4d8/matrix.txt` (forex majors)
- `artifacts/runs/31dcff1740e7b70bc2e1c6cc58be5dba08cdeaff8183602987f0a2f7a7bd66c5/matrix.txt` (forex minors)
- `artifacts/runs/a7455dfbf0cbcdf5f29e5066f51a848e55fd369a1201082d7cf1aeabf22dcb25/matrix.txt` (crypto spot majors)
- `artifacts/runs/bd825bc7b6dfbd8329bba79db08114288c33dbf5941f046382653d96b29e3473/matrix.txt` (crypto perp majors)
- `artifacts/runs/e91580cb1c2c036c2c8805da1b839e6d1f8b712281611ee0101a17db1b8b7912/matrix.txt` (crypto spot minors)
- `artifacts/runs/8d52ec36b3e601a0f4b88509f19e528d536f1d804d31509109460d9abd3021f2/matrix.txt` (crypto perp minors)

Matrix render note:
- Ensure factor cells never truncate into `|…` (e.g. `🟢|🟢|🟢` must render fully for MA/ROC too).

## Cleanup workflow

Safe default cleanup (caches only):
```bash
scripts/clean-workspace.sh
```

If you need to reset local Prefect state too:
```bash
scripts/clean-workspace.sh --prefect
```

## Workflow engine options (research)

Candidates to evaluate as Prefect alternatives:
- Dagu: file-based single-binary YAML DAG runner (GPL-3.0)
- Hatchet: Postgres-backed durable queue + workflows (MIT)
- Windmill: Postgres-backed platform for scripts/workflows/UIs (AGPL + additional CE terms)

## Market risk overlay (planned)

Goal: add a small macro/market-risk opportunity scan (NQ/ES/VIX/DXY) using the same `data` + `analytics --matrix` pipelines.

Change package: `docs/openspec/changes/add-market-risk-opportunity-scanner/`

Reality check (TradingView endpoints):
- `CME_MINI:ES1!` and `CME_MINI:NQ1!` are available via `asset_type=futures`.
- VIX futures continuous is `CBOE:VX1!` on the futures endpoint (not `CBOE:VIX1!`).
- `TVC:DXY` is available via `asset_type=stock`.

Prefect validation commands:
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type futures \
  --pairs CME_MINI:ES1! CME_MINI:NQ1! CBOE:VX1! \
  --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type futures \
  --pairs CME_MINI:ES1! CME_MINI:NQ1! CBOE:VX1! \
  --timeframes 240,60,15 --pipeline analytics --matrix --limit 10

uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type stock \
  --pairs TVC:DXY \
  --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type stock \
  --pairs TVC:DXY \
  --timeframes 240,60,15 --pipeline analytics --matrix --limit 10
```

Latest market-risk matrices:
- `artifacts/runs/73ae50e4e6c8a3fd1cb2e8121e42d3de7b9533d967442b80611a0239f785c3cc/matrix.txt` (futures: ES/NQ/VX)
- `artifacts/runs/5b87112bee57b85102dce487d4ff8473d7e2206d7875d5dafa3499276c499165/matrix.txt` (stock: DXY)

Latest market-risk matrix review:
- Futures basket renders 3 rows (ES1!/NQ1!/VX1!) with no `|…` truncation.
- DXY renders 1 row with full factor cells (e.g. `🟢|🟢|🟢`).

Iceberg validation queries:
- `uv run tvscreener-scan query tvscreener.signals_latest --sql "SELECT asset_type, count(*) AS n FROM df GROUP BY 1"`
- `uv run tvscreener-scan query tvscreener.signals_latest --sql "SELECT venue, count(*) AS n FROM df WHERE asset_type='crypto' GROUP BY 1"`

Runs table audit query:
- `uv run tvscreener-scan query tvscreener.runs --sql "SELECT asset_type, universe, instrument_type, pipeline_mode_executed, success, result_count, started_at_utc FROM df ORDER BY started_at_utc DESC LIMIT 20"`

Next: crypto screeners
- Treat base/largecap/snapshot as the crypto equivalents of forex majors/minors-style selectors.
- Keep volatility and strategy logic in analytics rankers/filters.

## Validation plan: Binance majors/minors matrix rerun (spot + perp)

Goal: rerun end-to-end `data` then `analytics --matrix` for Binance crypto majors/minors (spot + perp) and confirm:
- Iceberg `signals_latest` is populated for each instrument type
- Analytics-only rerenders (`--pipeline analytics`) produce ranked results
- Matrix view matches forex confluence format and uses venue-stripped `PAIR` labels

Default runner: Prefect (server + runner). Use `--runner local` explicitly only for fallback/debug.

Local runner is never implied; it must be selected explicitly via `--runner local`.

Start a local Prefect server (local/dev):
```bash
export PREFECT_HOME="$PWD/.prefect-home"
uv run prefect server start --host 127.0.0.1 --port 4200 --background
export PREFECT_API_URL="http://127.0.0.1:4200/api"
```

Commands (run sequentially when using legacy Iceberg tables):

### Data (Bronze/Silver/Gold publish)
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --pipeline data
```

### Analytics (matrix rerender from Iceberg)
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
```

### Local fallback (explicit)
```bash
uv run tvscreener-scan --runner local --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner local --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner local --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline data
uv run tvscreener-scan --runner local --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --pipeline data

uv run tvscreener-scan --runner local --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
uv run tvscreener-scan --runner local --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
uv run tvscreener-scan --runner local --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
uv run tvscreener-scan --runner local --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
```

Latest Prefect parity run artifacts (matrix):
- `artifacts/runs/a7455dfbf0cbcdf5f29e5066f51a848e55fd369a1201082d7cf1aeabf22dcb25/matrix.txt` (spot majors)
- `artifacts/runs/bd825bc7b6dfbd8329bba79db08114288c33dbf5941f046382653d96b29e3473/matrix.txt` (perp majors)
- `artifacts/runs/e91580cb1c2c036c2c8805da1b839e6d1f8b712281611ee0101a17db1b8b7912/matrix.txt` (spot minors)
- `artifacts/runs/8d52ec36b3e601a0f4b88509f19e528d536f1d804d31509109460d9abd3021f2/matrix.txt` (perp minors)

## Forex universe audit (majors/minors)

Universe resolution (pre-network):
- Majors: `EURUSD, GBPUSD, USDJPY, USDCHF, USDCAD, AUDUSD, NZDUSD`
- Minors: the full 7-currency cross set excluding `USD` (21 unique crosses)

Pre-analytics filtering (forex scans):
- Expands each pair across preferred exchanges into tickers like `OANDA:EURUSD`.
- Filters scan rows by `contract_type` (default `cfd`).
- Normalizes/deduplicates to one best row per `PAIR` using canonical name, `EXCHANGE_PRIORITY`, and volume.

Smoke validation (matrix view):
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe majors --timeframes 240,60,15 --pipeline analytics --matrix --limit 20
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type forex --universe minors --timeframes 240,60,15 --pipeline analytics --matrix --limit 20
```

### Sanity queries
```bash
uv run tvscreener-scan query tvscreener.runs \
  --sql "SELECT asset_type, universe, instrument_type, pipeline_mode_executed, success, result_count, started_at_utc FROM df WHERE asset_type='crypto' ORDER BY started_at_utc DESC LIMIT 20"
```

Spot top100 quote overview:
- Use the DuckDB report and read the `binance_spot_top100` quote breakdown in `report.md`.
- This summarizes which quote assets dominate membership and how many duplicate bases exist due to multi-quote listings.

Latest report artifacts:
- `artifacts/reports/binance-universes/20260310-201334/report.json`
- `artifacts/reports/binance-universes/20260310-201334/report.md`

Latest report artifacts (with spot top100 quote overview):
- `artifacts/reports/binance-universes/20260310-205526/report.json`
- `artifacts/reports/binance-universes/20260310-205526/report.md`

Latest report artifacts (spot/perp top100 now USDT/USDC only):
- `artifacts/reports/binance-universes/20260310-221631/report.json`
- `artifacts/reports/binance-universes/20260310-221631/report.md`

Latest report artifacts (includes spot vs perp parity table):
- `artifacts/reports/binance-universes/20260310-223139/report.json`
- `artifacts/reports/binance-universes/20260310-223139/report.md`

Latest report artifacts (includes volume distributions + top-assets tables):
- `artifacts/reports/binance-universes/20260310-224626/report.json`
- `artifacts/reports/binance-universes/20260310-224626/report.md`

Latest report artifacts (includes full per-asset volume parquet tables):
- `artifacts/reports/binance-universes/20260311-003025/report.json`
- `artifacts/reports/binance-universes/20260311-003025/report.md`

Latest report artifacts (includes risky-assets view + history_days):
- `artifacts/reports/binance-universes/20260311-011802/report.json`
- `artifacts/reports/binance-universes/20260311-011802/report.md`

Latest report artifacts (post strategy-base review refresh):
- `artifacts/reports/binance-universes/20260311-013632/report.json`
- `artifacts/reports/binance-universes/20260311-013632/report.md`

Latest report artifacts (generated via `review` pipeline):
- `artifacts/reports/binance-universes/20260311-014745/report.json`
- `artifacts/reports/binance-universes/20260311-014745/report.md`

Latest report artifacts (includes spot quote/volume breakdown):
- `artifacts/reports/binance-universes/20260311-083244/report.json`
- `artifacts/reports/binance-universes/20260311-083244/report.md`

Latest report artifacts (top100 underfill fix + diagnostics):
- `artifacts/reports/binance-universes/20260311-150122/report.json`
- `artifacts/reports/binance-universes/20260311-150122/report.md`

Latest report artifacts (strict review run):
- `artifacts/reports/binance-universes/20260311-150549/report.json`
- `artifacts/reports/binance-universes/20260311-150549/report.md`

Latest report artifacts (base-universe focus: volume + exclusions + dedup):
- `artifacts/reports/binance-universes/20260311-160716/report.json`
- `artifacts/reports/binance-universes/20260311-160716/report.md`

Latest report artifacts (readiness refresh):
- `artifacts/reports/binance-universes/20260312-104708/report.json`
- `artifacts/reports/binance-universes/20260312-104708/report.md`

Latest report artifacts (includes `Strategy Readiness` table):
- `artifacts/reports/binance-universes/20260312-151844/report.json`
- `artifacts/reports/binance-universes/20260312-151844/report.md`

Latest report artifacts (post universe-aliases update):
- `artifacts/reports/binance-universes/20260312-154232/report.json`
- `artifacts/reports/binance-universes/20260312-154232/report.md`

Latest report artifacts (includes majors/minors universes):
- `artifacts/reports/binance-universes/20260312-162057/report.json`
- `artifacts/reports/binance-universes/20260312-162057/report.md`

Latest report artifacts (majors readiness threshold updated):
- `artifacts/reports/binance-universes/20260312-162451/report.json`
- `artifacts/reports/binance-universes/20260312-162451/report.md`

Latest report artifacts (includes `Scanner Readiness` table):
- `artifacts/reports/binance-universes/20260312-163451/report.json`
- `artifacts/reports/binance-universes/20260312-163451/report.md`

Latest report artifacts (crypto majors now opportunity-ready heuristic):
- `artifacts/reports/binance-universes/20260312-165245/report.json`
- `artifacts/reports/binance-universes/20260312-165245/report.md`

Latest report artifacts (review defaults to screeners-only):
- `artifacts/reports/binance-universes/20260312-215701/report.json`
- `artifacts/reports/binance-universes/20260312-215701/report.md`

Latest report artifacts (review with `--include-all`):
- `artifacts/reports/binance-universes/20260312-215703/report.json`
- `artifacts/reports/binance-universes/20260312-215703/report.md`

Current base universes (recommended for strategy inputs):
- `binance_{spot,perp}_tradeable_base`: liquid + quote-restricted + excluded bases + base de-dup + short-history non-mcap exclusion.
- `binance_{spot,perp}_tradeable_mcap_cs`: market-cap anchored cross-section (mcap top100 bases intersected with tradeable gates).

Readiness snapshot (from latest report):
- `tradeable_base`: spot=90 bases (excluded_risky=23), perp=79 bases (excluded_risky=21), overlap_bases=60, duplicates=0.
- `tradeable_mcap_cs`: spot=28 bases, perp=26 bases, overlap_bases=24, duplicates=0.

Universe roles (not strategy bases by default):
- `binance_{spot,perp}_top100`: volume snapshot after gates; useful for monitoring and ad-hoc exploration.
- `binance_{spot,perp}_mcap_top100`: mapping coverage/audit tool; expect `missing_bases`.

Readiness table:
- Use `## Strategy Readiness` in the DuckDB report for a one-glance check of quote purity, dedup, and basic count thresholds for the strategy base universes.

Scanner readiness:
- Use `## Scanner Readiness` to assess whether a universe is suitable for the opportunity scanner (liquidity distribution) vs strategy scanners (dedup + quote purity + anchors).

Top100 underfill fix:
- `binance_{spot,perp}_top100` now focuses on liquidity/tradability: quote allowlist, min volume, exclusions, and base de-dup.
- Use `## Top100 Diagnostics` to see candidate counts through each step.

Latest breakdown takeaways (from `artifacts/reports/binance-universes/20260311-083244/report.md`):
- Spot quote composition: all spot universes are USDT-only except `binance_spot_top100` which has USDC spillover (USDT=52, USDC=6).
- Spot `total_quote_volume_usd` (sum across members): `spot_mcap_top100` ~5.81B, `spot_tradeable_base` ~4.62B, `spot_cs_momentum` ~4.18B, `spot_tradeable_mcap_cs` ~4.07B, `spot_top100` ~0.73B.
- Underfill persists for `*_top100` due to filters + TradingView results (spot=58, perp=88); treat it as a market snapshot, not a guaranteed-size base.
- Spot/perp base overlap (bases): `tradeable_base` overlap_bases=60; `top100` overlap_bases=44; `tradeable_mcap_cs` overlap_bases=26.

Spot vs perp audit checklist:
- Confirm quote composition (spot top100 should be USDT/USDC only).
- Confirm perp tickers end with `.P` and spot tickers do not.
- Compare spot vs perp parity by family (base overlap + median liquidity/volatility) using `## Spot vs Perp Parity`.
- Treat `*_mcap_top100` and `*_tradeable_mcap_cs` mapping loss (`missing_bases`) as expected; watch for regressions.

Volume distribution review:
- Use `## Volume Percentiles` to compare distribution shape per universe.
- Use `## Top Volume Assets` to spot concentration and outliers per universe.
- Use `## All Asset Volumes` and open the parquet files for a full per-asset view.

Risky asset review (tradeable base):
- See `excluded_risky` inside `artifacts/audits/binance-universes/binance_{spot,perp}_tradeable_base/universe.json`.
- See `risky_assets.parquet` in the DuckDB report output; it flags non-mcap-top100 bases present in tradeable universes.

Strategy base review:
- Use `binance_{spot,perp}_tradeable_base` as the default shared base for strategy research.
- Apply strategy-specific filters/rankers in analytics (DuckDB) to derive TSMOM/TSMR/CSMOM/CSMR candidate sets.
- For cross-sectional strategies, optionally swap base universe to `binance_{spot,perp}_tradeable_mcap_cs` (market-cap anchored) or apply an analytics-stage market-cap filter.

Current parity snapshot (see report):
- `top100`: spot bases=82 vs perp bases=93 (overlap_bases=60), duplicates: spot=18, perp=7.
- `tradeable_base`: spot bases=106 vs perp bases=102 (overlap_bases=70).

Key findings (from audit + DuckDB report):
- `binance_spot_top100` is not USD-quote-pure (TRY/JPY/BRL/EUR) and has many duplicate bases (USDT + USDC + fiat quotes).
- `binance_{spot,perp}_tradeable_base` is quote-restricted (USDT/USDC allowlist) and one-per-base (no base duplicates), making it a better strategy base.
- Market-cap-seeded universes remain mapping-lossy (`missing_bases` large), so treat them as coverage/audit tools; use `*_tradeable_mcap_cs` when you need a tradeable market-cap cross-section.

Planned update (implemented):
- Restrict `binance_{spot,perp}_top100` to `USDT`/`USDC` quotes for USD alignment.

Issues spotted:
- Market-cap-seeded universes still show high base->market mapping loss (`missing_bases`) even with `quote_assets` fallback.
- CS momentum universes intentionally add eligibility gates; `missing_bases` is expected to be large.
- Tradeable base universes are stable and strategy-ready, but not market-cap anchored.

Additional issue spotted:
- `binance_spot_top100` includes many non-USD quote assets (e.g. `TRY`, `JPY`, `BRL`, `EUR`) while perps are almost entirely `USDT/USDC`.
  - Recommendation: use `*_tradeable_base` / `*_tradeable_mcap_cs` for strategy work; treat `*_top100` as an opportunity-only universe unless we add a USD-only variant.

Fixes applied:
- Added `quote_assets` mapping with fallback (`USDT` then `USDC`) for `*_mcap_top100` and `*_cs_momentum`.
- Added `included_bases` and `missing_bases` to `universe.json` to audit mapping coverage at the base-asset level.

## Next: strategy layering on Binance universes

Plan: add strategy analytics layers for:
- TSMOM, TSMR
- CSMOM, CSMR

And add datasets required for ICT/SMC + volume profile:
- `market_bars` (OHLCV)
- derived `smc_features` and `volume_profile`

OpenSpec: `docs/openspec/changes/add-crypto-strategy-layering-ict-smc-volume-profile/`

## Next: tradeable market-cap CS universes

Plan: build `binance_{spot,perp}_tradeable_mcap_cs` as the 2nd-tier cross-sectional universe:
- seed from market-cap top 100
- restrict to tradeable-base gates
- use for CSMOM/CSMR

OpenSpec: `docs/openspec/changes/add-binance-tradeable-mcap-cross-section-universe/`

Tuning applied (spot-only):
- `binance_spot_top100` min volume: `2_500_000`
- `binance_spot_cs_momentum` min volume: `1_700_000`

## Research notes (TradingView crypto spot/perps)

Empirical TradingView results:
- Spot tickers like `BINANCE:BTCUSDT` appear in `CryptoScreener` with:
  - `Exchange=BINANCE`, `Type=spot`, `Subtype=crypto`
- Perps are also accessible via `CryptoScreener` by searching `PERP`, and appear as symbols ending in `.P`:
  - e.g. `BINANCE:BTCUSDT.P` with `Exchange=BINANCE`, `Type=swap`, `Subtype=crypto`

Selection columns available in `CryptoField`:
- `VOLUME_24H_IN_USD` (`Volume 24h in USD`)
- `PRICE` (`Price` / `close`)
- `HIGH`, `LOW`
- `EXCHANGE`, `TYPE`, `SUBTYPE`

Volatility proxy definition for filtering:
- prefer TradingView native `Volatility` (`Volatility.D`)
- fallback proxy: `volatility_24h_pct = (High - Low) / Price * 100`

## Brainstorm: scalable table naming

Problem: as we add asset types and dataset types, a single shared `tvscreener.bronze|silver|gold` table forces schema drift
and nullable columns.

Candidate namespace layout (logical):
- `tvscreener.<asset_type>.<instrument_type>.<stage>.<dataset>`
  - ex: `tvscreener.crypto.spot.bronze.screener_snapshot`
  - ex: `tvscreener.crypto.perp.gold.screener_snapshot`

Compatibility encoding (physical, single-level namespace):
- `tvscreener_<asset_type>_<instrument_type>_<stage>.<dataset>`

OpenSpec: `docs/openspec/changes/refactor-lakehouse-namespace-layout/`

Build status:
- Implemented a table-id resolver with `TVSCREENER_LAKEHOUSE_LAYOUT` (`legacy|scalable`).
- Scalable physical encoding uses single-level namespaces:
  - `tvscreener_<asset_type>_<instrument_type>_<stage>.<dataset>`
  - product tables: `tvscreener_<asset_type>_<instrument_type>_product.<dataset>`
- Data run (Prefect server): completed; wrote `tvscreener.bronze` append and overwrote `silver`, `gold`, `signals_batch`, `signals_latest`.
  - Log: `artifacts/matrix/forex_all_data_prefect_server.log`
- Opportunity analytics matrix (Prefect server): rendered to logs and persisted as `matrix.txt`.
  - Log: `artifacts/matrix/forex_all_opportunity_analytics_prefect_server_3.log`
  - Artifact: `artifacts/prefect/4dee96c25388f26a512b785ccc7388c58f73388b5446704f332e5d483b7428d5/matrix.txt`
- Strategy analytics matrix (Prefect server): rendered to logs and persisted as `matrix.txt`.
  - Log: `artifacts/matrix/forex_all_strategy_analytics_prefect_server_2.log`
  - Artifact: `artifacts/prefect/2609f3a93d1ecdceab2312c110626d48d9d8d576e39e2da1753578377365135d/matrix.txt`
