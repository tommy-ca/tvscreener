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

## Review plan: Binance crypto universes (6)

Current universes (spot + perp variants):
- `binance_{spot,perp}_top100`: TradingView crypto /scan rank by `Volume 24h in USD`, selection-time filters (min volume + min volatility).
- `binance_{spot,perp}_mcap_top100`: TradingView coin /scan market-cap seed -> map to Binance tickers; no filters at selection time.
- `binance_{spot,perp}_cs_momentum`: market-cap seed -> exclude stables/wrapped -> liquidity gate; ordered by USD trading value.

Base-universe recommendation:
- Use `binance_{spot,perp}_mcap_top100` as the broad, reproducible **base universe** (raw membership + requested/missing auditing).
- Derive strategy-specific candidates from the base:
  - momentum: `binance_{spot,perp}_cs_momentum` (eligibility gate only)
  - short-term opportunity: `binance_{spot,perp}_top100` (selection-time gates)

Audit checklist for each universe:
- Determinism: `universe.json` written, includes `requested_tickers` and `missing_tickers`.
- Instrument isolation: `instrument_type` is correct (`spot` vs `perp`).
- Eligibility vs ranking: selection-time filtering kept minimal for “base” universes.

Audit snapshot (current):
Audit snapshot (current):
- `binance_spot_top100`: 38
- `binance_perp_top100`: 40
- `binance_spot_mcap_top100`: 39
- `binance_perp_mcap_top100`: 34
- `binance_spot_cs_momentum`: 47
- `binance_perp_cs_momentum`: 48

Audit artifacts:
- `artifacts/audits/binance-universes/report.json`

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
