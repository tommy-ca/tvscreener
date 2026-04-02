# Plan: Forex all-universe matrix rerun + docs refresh

date: 2026-03-07
branch: feat/forex-strategy-scanner

## 2026-03-26: Audit snapshot (current truth)

This file includes historical notes from earlier iterations. Current validated direction:

- Track B is the active path: extensions-owned pipelines live under `extensions/`.
- Repo-local `tvscreener/` is treated as an upstream mirror; do not apply extensions-driven fixes there.
- Prefect orchestration, lakehouse writes, DuckDB analytics, and Prefect artifact publishing live in `extensions/`.
- When documentation conflicts, prefer the OpenSpec change packages under:
  - `docs/openspec/changes/refactor-extract-extensions-from-upstream/`
  - `docs/openspec/changes/refactor-prefect-composable-flows/`
  - `docs/openspec/changes/update-terminology-and-interfaces/`

## 2026-03-26: Migration plan (repo-local -> extensions)

Goal: stop relying on editing the repo-local `tvscreener/` tree for workflows.

1) Enforce upstream-only imports
- Keep `tvscreener_ext.upstream.ensure_upstream_tvscreener()` strict (fail fast on `<repo>/tvscreener/...`).
- Verification gate:
  - `uv run --project extensions python extensions/tools/check_upstream_tvscreener_resolution.py`

2) Move workflow-critical behavior into `extensions/`
- Prefect flows, deployments, workers, and artifacts live under `extensions/src/tvscreener_ext/prefect/`.
- DuckDB semantic table generation for Prefect table artifacts lives under `extensions/src/tvscreener_ext/semantic/`.
- Lakehouse contract and writes are owned by `extensions/src/tvscreener_ext/lakehouse.py`.

3) Update docs/runbooks
- Prefer `uv run --project extensions ...` commands for operator workflows.
- Treat repo-local `tvscreener-scan` usage as development/audit-only.

4) Sync-back strategy
- When upstream publishes equivalent pipeline/lakehouse/Prefect runner surface area, delete duplicated core pipeline
  code from `extensions/` and keep only orchestration templates + ops CLIs.

## 2026-03-25: Essential pipelines validation (Prefect server)

Target:
- Rerun **data + analytics** (`--pipeline both`) using the Iceberg catalog.
- Rerender **analytics-only** matrices (`--pipeline analytics`) to validate the read path.

Prefect:
```bash
cp .env.example .env
uv run python3 workflows/prefect/prefectctl.py server start --background
uv run python3 workflows/prefect/prefectctl.py check --limit 5 --lookahead-minutes 30
```

Analytics-only rerenders (`--pipeline analytics --matrix --limit 50`):
- Forex majors: `artifacts/runs/70696cd35fb6f9f781e621a79fe0df995e70adb6925ed81052ba9aaad8fcc890/run_result.json`
- Forex minors: `artifacts/runs/2ed6f942ae981b9c26606953e7a5a679efc1ed5526bbae63953cebc35517393f/run_result.json`
- Crypto spot majors: `artifacts/runs/b966754797cb6428bfe242b903c82119bcd923224be60299f8c3c8c6883d1e8e/run_result.json`
- Crypto perp majors: `artifacts/runs/02cdbd5ea6d54772f41e63878f3ece1df983038d485d12daf1d44212a99d984b/run_result.json`
- Crypto spot minors: `artifacts/runs/3f18bd080d54f2118eeee02be0f79f9eab605cfe95d8977de244d7051a577388/run_result.json`
- Crypto perp minors: `artifacts/runs/6b1f70993b3d2628e7f67014a74e41b1d6073ebc1c038fd18153e89bee97d5ed/run_result.json`
- Market risk basket: `artifacts/runs/504ad7c6595b6e54d95243e9919d623e0bc7503acb42151fa5eab432c28dbaf1/run_result.json`

Full refresh (`--pipeline both --matrix --limit 50`), verified Iceberg writes to:
`tvscreener.bronze`, `tvscreener.silver`, `tvscreener.gold`, `tvscreener.signals_batch`, `tvscreener.signals_latest`, and audit appends to `tvscreener.runs`.

- Forex majors: `artifacts/runs/b0621cdacfc9e3f4c2180c479b9cba5f6132525c33f83e512c440caea350fb0d/run_result.json`
- Forex minors: `artifacts/runs/b5f5d2522b7ce46250203f4e81e86079fb2287f630b73e289407a3f2cf090c09/run_result.json`
- Crypto spot majors: `artifacts/runs/08612e192e148ce072ef2c3cd070fb932b200f445d41662cfd0506f11a44672f/run_result.json`
- Crypto perp majors: `artifacts/runs/d2a32c39ba1c443342705ac45c3befc996917c8b08c25d437743728f3404bec3/run_result.json`
- Crypto spot minors: `artifacts/runs/676161ff4943e75fdeb2eabf6dc440b19fe5edf24b63e2db216aebffa53febfa/run_result.json`
- Crypto perp minors: `artifacts/runs/b21f48952ba7b6efa086281ac58b87b6fd05662a1b8abc65aec9ed2e02c9c6d6/run_result.json`
- Market risk basket: `artifacts/runs/742c343a8e2440a17409d1fbe6e6f332ec71998f9dd4c575c850a0414dad8b2e/run_result.json`

Next validation steps:
- Worker engine: apply deployments and run `data` + `analytics` workers; validate scheduled runs appear in `prefectctl.py check`.
- Iceberg/DuckDB: run a small set of `tvscreener-scan query ...` checks against `tvscreener.runs` and `tvscreener.signals_latest`.
- Packaging: extract workflows + custom orchestration into an extensions distribution that depends on installed upstream `tvscreener`.

### 2026-03-25: Extensions execution plan (upstream-first)

Goal:
- Ship `extensions/` as a standalone uv project (`tvscreener-ext`).
- Ensure extension CLIs resolve upstream `tvscreener` from site-packages even when invoked inside this repo.
- Provide operator runset + Prefect scheduling helpers.

Progress:
- [x] Added `extensions/pyproject.toml` and `extensions/src/tvscreener_ext/*`.
- [x] Added upstream-import guard: `extensions/src/tvscreener_ext/upstream.py`.
- [x] Added CLIs:
  - `tvscreener-ext-scan` (extensions-owned pipeline runner)
  - `tvscreener-prefectctl` (server/pool/worker/check)
  - `tvscreener-deploy-schedules` (runner/worker deployments using bundled batches)
  - `tvscreener-ext-validate` (essential runset)

Next:
- [ ] Validate upstream resolution from repo root:
  - `uv run --project extensions python -c "from tvscreener_ext.upstream import ensure_upstream_tvscreener; ensure_upstream_tvscreener(); import tvscreener; print(tvscreener.__file__)"`
- [ ] Validate Prefect helpers from extensions:
  - `uv run --project extensions --extra prefect tvscreener-prefectctl server start --background`
  - `uv run --project extensions --extra prefect tvscreener-prefectctl pool`
  - `uv run --project extensions --extra prefect tvscreener-prefectctl check --limit 5 --lookahead-minutes 30`
- [ ] Validate essential runset from extensions:
  - `uv run --project extensions --extra prefect tvscreener-ext-validate --mode both`
  - `uv run --project extensions --extra prefect tvscreener-ext-validate --mode analytics`

Blocker discovered:
- The installed package-index `tvscreener==0.2.1` does not ship `tvscreener-scan` or `tvscreener.lib.*`.
- This is why Track B (extensions-owned pipelines) is used.

Rescheduled plan (two tracks):

- Track A: thin-wrapper extensions (preferred if upstream publishes workflows)
  - [ ] Pin/choose an upstream `tvscreener` version that ships the required pipeline + CLI surface area
  - [ ] Re-run essential pipelines via `uv run --project extensions --extra prefect tvscreener-ext-validate`
  - [ ] Apply deployments via `uv run --project extensions --extra prefect tvscreener-deploy-schedules --apply --engine worker --mode both`
  - [ ] Start workers via `uv run --project extensions --extra prefect tvscreener-prefectctl worker ...`

- Track B: extensions-owned pipelines (if upstream stays lightweight)
  - [x] Implement `PipelineRunSpec` + runner inside `tvscreener-ext`
  - [x] Implement Iceberg persistence + DuckDB analytics inside `tvscreener-ext`
  - [x] Wire Prefect flow(s) to extensions runner
  - [ ] Re-run essential pipelines and scheduled deployments using extensions-only code

Track B runbook (extensions-owned pipelines):

```bash
uv run --project extensions --extra prefect tvscreener-prefectctl server start --background
uv run --project extensions --extra prefect tvscreener-prefectctl pool

# In-process Prefect validation (creates flow runs in server)
uv run --project extensions --extra prefect tvscreener-ext-validate --runner prefect --mode both --limit 10
uv run --project extensions --extra prefect tvscreener-ext-validate --runner prefect --mode analytics --limit 10

# Worker engine scheduling
uv run --project extensions --extra prefect tvscreener-deploy-schedules --apply --engine worker --mode both --work-pool tvscreener
uv run --project extensions --extra prefect tvscreener-prefectctl worker --queue data --limit 1
uv run --project extensions --extra prefect tvscreener-prefectctl worker --queue analytics --limit 2

uv run --project extensions --extra prefect tvscreener-prefectctl check --limit 10 --lookahead-minutes 90
```

Track B smoke validation (2026-03-25):
- Local runner (Iceberg writes + DuckDB analytics):
  - Forex majors `both`: `artifacts/runs/f152e8e9c9178de625ece694a2013c00eb216c77553724d227a26874983e8e46/run_result.json`
  - Forex majors `analytics`: `artifacts/runs/afe0ccb8be89e2342b6f09171e57b9a63450d53703d8b52214543b95b5e1fb51/run_result.json`
- Prefect runner (server-backed flow runs) essential runset `analytics` with `limit=5`:
  - `artifacts/runs/bb2d341dd44fb67821f0431e80695eeb491610871080c558ae1345dbe6a035a0/run_result.json`
  - `artifacts/runs/e3605228a6957fa9966c7cb06ab2f334373487b278f720d55829450fdc6ced26/run_result.json`
  - `artifacts/runs/a7762f7bfa362dc29a991c571192af332dbd0ec8b55c68d63e910cfffa5b4897/run_result.json`
  - `artifacts/runs/4e0799f4b69a775d4201d7fac62fabd89e6b4f35d16bcca7244be1e98d01b745/run_result.json`
  - `artifacts/runs/0e292f9ed8410b7167548959a7b202b3cad0516f523a33694cf67030b7de91ca/run_result.json`
  - `artifacts/runs/49d59cf639a14371d61aa8fcca09f99c2a731b89cc16a6c53586cdafeb0913e3/run_result.json`
  - `artifacts/runs/e931f3d361481841c17196dc63fc7eeac77f141043a111a90862a235d407f871/run_result.json`

Track B rerun (2026-03-25):
- Prefect runner essential runset `both` with `limit=50`:
  - `artifacts/runs/2787c4cf270e9ea0b31f4b537cbe6bfabb2705ded0fa3e252c6767db90026704/run_result.json`
  - `artifacts/runs/e40acdba96de4fae70fbd1728b4abab744e714c015188fc51c4edc86e1fca3a3/run_result.json`
  - `artifacts/runs/a231a20f1002c1726050b7983d2a70979084594c46406f30c92359d8a9ffab64/run_result.json`
  - `artifacts/runs/e407620d411cacf6c929c60401ca6c679a65fab2a855745d81286429dd263093/run_result.json`
  - `artifacts/runs/0b67507caf12ee7301768afa8812753791d3a57c56acc458770ab27c066028f6/run_result.json`
  - `artifacts/runs/d9b6ab9e575170e95fb4028a5a0c45c78a2497e7373376e2ef840b67262b62d5/run_result.json`
  - `artifacts/runs/481967a19f2cf08e1a427228b03a808af036d2cb81d260a2a7cce6c6ad0c5f9c/run_result.json`

Track B reschedule attempt (Prefect worker engine):
- Applied `mode=both` deployments to work pool `tvscreener`.
- Prefect check shows deployments exist but `status=NOT_READY` and `scheduled_runs=count 0`.
- Root cause: Prefect 3 requires an image or remote storage strategy for worker deployments; file-path deployments
  without storage/image do not become READY.
- Next: pick a deployment packaging strategy (docker image or remote storage pull steps) and re-apply deployments.

Update (2026-03-25):
- Confirmed Prefect worker deployments remain `status=NOT_READY` even when using `entrypoint_type=MODULE_PATH`.
- Confirmed that `prefect.runner.Runner.start` is a coroutine and must be awaited (fixed in
  `extensions/src/tvscreener_ext/deploy_schedules.py`).
- `Runner.start(run_once=True)` pauses deployments on exit; avoid using it as a scheduling verification step.

Update (2026-03-25): Prefect server + scheduling reset
- Discovered a stale Prefect server process from a different checkout was bound to port 4200.
- Discovered Prefect OSS server on SQLite can hit `database is locked` / HTTP 503 when multiple Prefect processes
  share the same `PREFECT_HOME` and the DB grows large.
- Recovery: stop/kill Prefect workers + runner + server, move `.prefect-home/` aside, recreate it, and restart the
  server.
- After reset, worker-engine scheduling started materializing scheduled flow runs:
  - `uv run --project extensions --extra prefect tvscreener-prefectctl check --pool tvscreener --work-queue data,analytics --limit 10 --lookahead-minutes 180`
  - Example output: `scheduled_runs=count 6` (forex/crypto) and later market-risk also appeared after scheduler loop.

Track B rerun (2026-03-25, fresh Prefect server):
- Analytics-only essential runset `limit=10` completed:
  - `artifacts/runs/ea728a862ccf4cde62a9e7ba809915d90dbfea9a980a222def5e305947ec5bcc/run_result.json`
  - `artifacts/runs/fd14db205290c808eb9e5fed1af32564d95d16df7ba56397d2e44009b57d383f/run_result.json`
  - `artifacts/runs/48b3cab2071ab65e5d6f7e675d7c0396afc2bd84dbc40c5fd3d15d4a5f60d052/run_result.json`
  - `artifacts/runs/ad8b6a3d05aedc13ec44b6954a9117f6e1dd7c3d3980eec907b93483ee0523ef/run_result.json`
  - `artifacts/runs/aebe081b44106d1503d05f8ca5d902b6c653371e558e1b38d6012af3b7909d9e/run_result.json`
  - `artifacts/runs/334ab4655c995dea0f45332100e2bbafa17a79702222ec0b45f01115a77094ee/run_result.json`
  - `artifacts/runs/3906797c45ec66db2ce956ba8e173b209aa027e5d10325970226eb1e9e22d148/run_result.json`

Track B reschedule (2026-03-25, fresh Prefect server + scheduler):
- Applied worker deployments (mode=both):
  - Forex both: deployment id `59a10416-f93c-4f48-9c2a-5b8d5f48f351`
  - Crypto both: deployment id `8820d787-fd56-4cbc-b1d0-6f4f20f37c03`
  - Market risk both: deployment id `e0bb42e1-ac4a-45c4-a260-982d78099c40`
- Verified scheduled runs materialize in work queues via `tvscreener-prefectctl check`.

Track B reschedule execution (2026-03-25):
- Ran a `ProcessWorker` once (`--run-once`) to execute one scheduled run.
- First attempt failed immediately due to Prefect flow run naming: `tvscreener-batch` used
  `flow_run_name="tvscreener-batch-{batch_id}"` but `batch_id` is not a flow parameter, causing `KeyError: 'batch_id'`.
  - Worker log: `artifacts/prefect/worker-data-runonce.log`
  - Fix: update `extensions/src/tvscreener_ext/prefect/run_batch.py` to use a parameter-based flow run name.

- After the fix, a worker successfully executed one scheduled run end-to-end (market risk, `both`):
  - Worker log: `artifacts/prefect/worker-data-runonce-2.log`
  - Run artifacts: `artifacts/runs/481967a19f2cf08e1a427228b03a808af036d2cb81d260a2a7cce6c6ad0c5f9c/run_result.json`

Environment parity updates (2026-03-25):
- Added `TVSCREENER_PREFECT_WORK_QUEUE=default` defaults and routed worker deployments to it.
- Added extensions default lakehouse base dir: `TVSCREENER_LAKEHOUSE_BASE_DIR=.tvscreener/lakehouse` (repo-local).

Prefect worker parity verification (2026-03-25):
- Re-applied worker deployments targeting the `default` queue and confirmed deployments are `status=READY`:
  - `uv run --project extensions --extra prefect tvscreener-deploy-schedules --apply --engine worker --mode both --work-pool tvscreener --work-queue default`
  - `uv run --project extensions --extra prefect tvscreener-prefectctl check --pool tvscreener --work-queue default --limit 10 --lookahead-minutes 180`

Lakehouse audit (repo-local base dir):
- Ran a local Track B run with explicit base dir:
  - `artifacts/runs/e09d25516610af9d888d144fe8f2618d20a0f82c00a37485ef0cc1dbbe9a2a29/run_result.json`
- Audited `signals_latest` grouping (repo-local lakehouse):
  - `TVSCREENER_LAKEHOUSE_BASE_DIR=.tvscreener/lakehouse uv run --project extensions tvscreener-ext-audit --groups 50`
- Repo-local table inventory after a single market-risk run:
  - `tvscreener.bronze` rows=12
  - `tvscreener.signals_latest` rows=4
  - `tvscreener.runs` rows=1

Analytics-only read-only check (repo-local lakehouse):
- Verified `signals_latest` `max(fetched_at_utc)` for stock/market_risk is unchanged by an analytics-only rerender.

Essential data pipeline check (2026-03-25, repo-local lakehouse):
- Ran data pipelines for:
  - forex majors/minors
  - crypto binance spot/perp majors/minors
- Verified `signals_latest` groups updated via `tvscreener-ext-audit`.

Analytics rerender + artifacts (2026-03-25):
- Ran analytics-only rerenders under Prefect for the essential runset (`limit=50`) with:
  - `TVSCREENER_PUBLISH_RESULTS_SUMMARY=1`
  - `TVSCREENER_PUBLISH_TABLE_ARTIFACTS=1`
- Verified per-run `matrix.md` is written under run artifacts:
  - `artifacts/runs/cc8c29c4a4de6158b357a68cfaabad04bc63524e452cfc3cb84ca562a95f0ae9/matrix.md`
  - `artifacts/runs/31e57d209cfa72b62c9890c388004dee662cee6b0bcf1af8d2829b832554189c/matrix.md`
  - `artifacts/runs/9a704781b4ad44da15d169c1c8db28eede98bda2f049e8df466d885d2998d4e4/matrix.md`
  - `artifacts/runs/ffb4402010132b077bad7099083f9aac25290d14722d68e1482bf907fe979516/matrix.md`
  - `artifacts/runs/7cfa07eeb8c6cd744f289da6da2dc8ed2d26f269415194cdda2d3a0efcb0d3cb/matrix.md`
  - `artifacts/runs/82ecf11ac72bfbe432d70853ee224c21af557d017cccdfc8c8107404b5a75d9c/matrix.md`
  - `artifacts/runs/ca42e453033023826290fb083b0e0f4a30f0f5eae9a93db0d650880d0c069fbd/matrix.md`

Prefect split deployments plan (2026-03-25):
- Deploy data pipelines separately for:
  - forex majors, forex minors
  - binance crypto spot majors, perp majors, spot minors, perp minors
- Deploy analytics pipelines separately for the same universes/instruments.
- Analytics deployments publish Prefect markdown + table artifacts.

Prefect split deployments applied (2026-03-25):
- Applied split data deployments (all on `default` queue):
  - `opportunity-forex-majors-data` id `4e060511-9e77-4d18-8cf3-2999ec0424b5`
  - `opportunity-forex-minors-data` id `81be130f-ee29-4692-aca5-b9b096767a65`
  - `opportunity-crypto-binance-spot-majors-data` id `558ddf6d-d880-4c34-b325-5bae1d781b37`
  - `opportunity-crypto-binance-perp-majors-data` id `44757527-d429-4664-b9c8-4001b23f9410`
  - `opportunity-crypto-binance-spot-minors-data` id `3b49c5c8-d90f-4507-9d23-2230a7f441de`
  - `opportunity-crypto-binance-perp-minors-data` id `27607c31-754e-4e01-bcd2-504b30a93212`
- Applied split analytics deployments (publish Prefect markdown + table artifacts):
  - `opportunity-forex-majors-analytics` id `05eb28b3-f5f6-48f3-9de2-dcb028464a4b`
  - `opportunity-forex-minors-analytics` id `bfd3eacd-3638-4eaa-b191-4c6263146f12`
  - `opportunity-crypto-binance-spot-majors-analytics` id `027752ee-802a-4369-9fc2-aef78bac367d`
  - `opportunity-crypto-binance-perp-majors-analytics` id `71392916-0eef-486f-b246-224affd13c49`
  - `opportunity-crypto-binance-spot-minors-analytics` id `0678640a-ae2c-4459-b751-c1c23d713816`
  - `opportunity-crypto-binance-perp-minors-analytics` id `ae52c564-9de1-41ea-96e9-65a41bb4909a`

Reschedule + proceed (2026-03-25):
- Rescheduled split deployments by re-applying `--mode split-data` and `--mode split-analytics`.
- Verified split deployments schedule onto work queue `default`.
- Proceeded by running a `process` worker on `default` queue and executing scheduled runs.
  - Worker log: `artifacts/prefect/worker-default-limit3.log`

Terminology standardization plan (2026-03-25):
- Add canonical terminology spec (Prefect-native terms + MLOps/DataOps mapping).
- Update existing specs/design docs to reference canonical `pipeline_mode` semantics.
- Prefer deterministic identifiers (`params_hash`, artifact keys, deployment names) and avoid citing Prefect-generated
  whimsical flow run names in docs.

Composable Prefect flows plan (2026-03-25):
- Audit legacy Prefect deployment scripts in `workflows/prefect/` and map them to extensions.
- Decompose the extensions Prefect flow into stage tasks:
  - data stage task
  - analytics stage task
- Keep `pipeline_mode=both` as legacy single-task by default; allow composition via `TVSCREENER_PREFECT_COMPOSE_BOTH=1`.

Composable Prefect flows evidence (2026-03-25):
- Ran a worker with `TVSCREENER_PREFECT_COMPOSE_BOTH=1` and observed explicit stage tasks in logs:
  - `run_data_stage` followed by `run_analytics_stage`
  - Worker log: `artifacts/prefect/worker-default-composeboth-limit5.log`
- Example composed flow run:
  - Prefect flow run id: `0545dd69-aa2d-416c-bb73-35a49bdb4958`

Cleanup/refactor pass (2026-03-25):
- Removed repo-root `Dockerfile` (keep `extensions/Dockerfile` as the packaging starting point).
- Updated `prefect.yaml` default work queue to `default`.
- Updated `tvscreener-prefectctl check` output to use `flow_run_id` rather than Prefect run names.
- Extracted Prefect stage tasks into `extensions/src/tvscreener_ext/prefect/stages.py` so flows can import/compose them.

Post-cleanup verification (2026-03-25):
- Verified `tvscreener-prefectctl check` prints `flow_run_id` (not Prefect run names) for scheduled runs.

Prefect queue hygiene (2026-03-25):
- Observed that scheduled runs can accumulate and become `Late`, delaying on-demand deployment runs.
- Added `tvscreener-prefectctl prune-late` and used it to cancel late scheduled runs on `default` queue.

Prefect native commands refactor (2026-03-25):
- Historical note: this was an intermediate step.
- Current direction: extensions wrappers do not shell out; they use the Prefect Python API client and worker classes.

Prefect wrappers: no subprocess (2026-03-25):
- Removed subprocess calls to Prefect CLI from extensions wrappers.
- `tvscreener-prefectctl` uses Prefect Python APIs:
  - server management via `prefect.cli.server.start/stop`
  - pool/queue creation via `PrefectClient.create_work_pool/create_work_queue`
  - worker execution via `prefect.workers.process.ProcessWorker`
  - check/prune via `PrefectClient` (`read_deployments`, `read_work_queue_by_name`, `get_scheduled_flow_runs_for_work_pool`, `set_flow_run_state`).

Prefect wrappers audit (2026-03-25):
- Confirmed `extensions/src/tvscreener_ext/prefect_check.py` no longer uses subprocess.
- Confirmed `extensions/src/tvscreener_ext/prefectctl.py` no longer shells out to `prefect`.

Prefect artifacts audit plan (2026-03-25):
- Ensure Prefect server is ready (`tvscreener-prefectctl server ensure --background`).
- Start `ProcessWorker` for `default` queue in background.
- Trigger data deployments for:
  - forex majors/minors
  - crypto binance spot/perp majors/minors
- Trigger analytics deployments for the same universes/instruments.
- List Prefect artifacts via API:
  - `tvscreener-prefectctl artifacts --type markdown --key-like tvscreener-matrix-%`
  - `tvscreener-prefectctl artifacts --type table --key-like tvscreener-results-%`

Prefect table artifacts fix (2026-03-25):
- Observed markdown artifacts existed but no `tvscreener-results-*` table artifacts.
- Root cause: `TVSCREENER_PUBLISH_TABLE_ARTIFACTS` env injection was not reliably present in process worker runtime.
- Fix: default Prefect stage tasks to publish table artifacts unless `TVSCREENER_PUBLISH_TABLE_ARTIFACTS=0`.
- Additional fix: Prefect Table artifacts require JSON-serializable values; datetimes must be coerced to ISO strings.

DuckDB semantic table artifacts (2026-03-25):
- Updated analytics pipeline to write semantic tables using DuckDB modeled queries:
  - `results_top_rows.json`
  - `results_grade_summary.json`
- Updated Prefect stage tasks to publish Table artifacts from those JSON tables (no pandas/parquet conversion).

Upstream isolation cleanup (2026-03-26):
- Reverted repo-local changes in `tvscreener/` so upstream remains untouched.
- Updated `pyproject.toml` ty configuration to exclude upstream pyiceberg callsites rather than patching upstream.

Extensions upstream import guard (2026-03-26):
- Hardened `tvscreener_ext.upstream.ensure_upstream_tvscreener()` to fail fast if resolution points at repo source.
- Updated `extensions/tools/check_upstream_tvscreener_resolution.py` to validate the guard.

Sync plan (2026-03-26):
- Treat extensions-owned pipelines as a bridge until upstream publishes equivalent modules.
- When upstream provides the pipeline runner + lakehouse + Prefect runner surface area, refactor extensions into a
  thin orchestration layer (deployments/batches/ops CLIs) and delete duplicate pipeline code.

Prefect server wrapper (2026-03-25):
- Observed `tvscreener-prefectctl server start --background` fails if port 4200 is already in use.
- Updated wrapper to catch Prefect CLI `SystemExit` and return non-zero with an error.

Track B rerun (2026-03-25, rerun #2):
- Prefect runner essential runset `both` started at ~11:37; last flow run in the sequence was still running when this
  log entry was written:
  - `prefect flow-run inspect aff53797-d5db-4af1-8e5c-8f7444f5db0c`
- The last run (crypto spot minors) appeared to hang; cancelled and reran locally with a smaller limit:
  - Crypto spot minors `both` (limit=10): `artifacts/runs/abbb384e7b72f2f197e7922b21bf027f727c787e077004b8e6558dd711f705ff/run_result.json`

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

## 2026-03-16: Scheduled deployments validation (data-first)

Goal: validate the Prefect scheduled deployments for:
- forex majors/minors
- Binance crypto spot/perp majors/minors
- market risk proxy basket

Workflow:
1) Confirm scheduled `pipeline_mode=data` runs are fresh via `tvscreener.runs`.
2) If stale, trigger the data batch deployments first.
3) Rerender the matrix via `pipeline_mode=analytics` for each universe.

Notes:
- Data-only schedules do not update analytics artifacts (`matrix.txt`, `*_results.parquet`).
- Scheduled runs should fail if Iceberg persistence fails (strict persist enabled for Prefect data tasks).

Commands (analytics rerender, matrix view):
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline analytics --asset-type forex --universe majors --timeframes 240,60,15 --matrix --limit 50
uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline analytics --asset-type forex --universe minors --timeframes 240,60,15 --matrix --limit 50

uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline analytics --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --matrix --limit 50
uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline analytics --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --matrix --limit 50
uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline analytics --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --matrix --limit 50
uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline analytics --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --matrix --limit 50

uv run tvscreener-scan --runner prefect --scanner opportunity --pipeline analytics --asset-type stock --universe market_risk --timeframes 240,60,15 --matrix --limit 50
```

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

Named universe shortcut:
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type stock \
  --universe market_risk \
  --timeframes 240,60,15 --pipeline analytics --matrix --limit 10
```

Latest market-risk matrices:
- `artifacts/runs/73ae50e4e6c8a3fd1cb2e8121e42d3de7b9533d967442b80611a0239f785c3cc/matrix.txt` (futures: ES/NQ/VX)
- `artifacts/runs/5b87112bee57b85102dce487d4ff8473d7e2206d7875d5dafa3499276c499165/matrix.txt` (stock: DXY)

Latest market-risk matrix review:
- Futures basket renders 3 rows (ES1!/NQ1!/VX1!) with no `|…` truncation.
- DXY renders 1 row with full factor cells (e.g. `🟢|🟢|🟢`).

Data-vs-matrix validation note:
- Futures basket currently returns null `Recommend.*|{tf}` and `Roc|{tf}` values, so the matrix is correctly all-neutral (`0/12`, `F`).
- Use stock proxies (e.g. `SPY`, `QQQ`, `TVC:VIX`, `TVC:DXY`) if the overlay must be matrix-informative.

Latest market-risk proxy basket matrix (stock):
- `artifacts/runs/24124097f596691e0f78e9c7b9e3871d2d16bfef3d522308b7ac457de011e0a6/matrix.txt` (SPY/QQQ/VIX/DXY)

## Prefect schedules (planned)

Goal: schedule periodic opportunity batch runs for:
- forex majors/minors
- binance crypto spot/perp majors/minors
- market risk proxy basket (`market_risk`)

Deploy helper: `workflows/prefect/deploy_schedules.py`

Validated scheduled deployment (data-only):
- `tvscreener-batch/opportunity-forex-majors-minors-data`
- Artifacts: `artifacts/runs/batch/forex-majors-minors-data/batch_result.json`

Validated scheduled deployments (data-only):
- `tvscreener-batch/opportunity-crypto-binance-majors-minors-data`
  - Artifacts: `artifacts/runs/batch/crypto-binance-majors-minors-data/batch_result.json`
- `tvscreener-batch/opportunity-market-risk-proxy-data`
  - Artifacts: `artifacts/runs/batch/market-risk-proxy-data/batch_result.json`

Validated on-demand analytics rerenders (matrix):
- `artifacts/runs/70696cd35fb6f9f781e621a79fe0df995e70adb6925ed81052ba9aaad8fcc890/matrix.txt` (forex majors)
- `artifacts/runs/2ed6f942ae981b9c26606953e7a5a679efc1ed5526bbae63953cebc35517393f/matrix.txt` (forex minors)
- `artifacts/runs/b966754797cb6428bfe242b903c82119bcd923224be60299f8c3c8c6883d1e8e/matrix.txt` (crypto spot majors)
- `artifacts/runs/02cdbd5ea6d54772f41e63878f3ece1df983038d485d12daf1d44212a99d984b/matrix.txt` (crypto perp majors)
- `artifacts/runs/3f18bd080d54f2118eeee02be0f79f9eab605cfe95d8977de244d7051a577388/matrix.txt` (crypto spot minors)
- `artifacts/runs/6b1f70993b3d2628e7f67014a74e41b1d6073ebc1c038fd18153e89bee97d5ed/matrix.txt` (crypto perp minors)
- `artifacts/runs/e6838f43888957085bd9576bd42d39aaeea2cba7df8e01c94b0e1425a2bf8b7f/matrix.txt` (market risk)

Data freshness check:
- Confirm `pipeline_mode_executed=data` runs are recent before rerendering analytics.

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

## 2026-04-01: API Validation & Testing Architecture Fixes

Goal: Address hanging tests, API validation mismatches, and filter collision bugs caused by incomplete monkeypatching.

Outcomes:
- **Test Environment Integrity**: Fixed hanging tests by ensuring `tvscreener_ext` is explicitly imported in test suites (`test_api_validation.py`). This guarantees monkeypatches (like the API data mock) take precedence over real external network calls, preventing 10-minute timeouts. Also corrected mock target paths to point to `tvscreener.util.get_columns_to_request` instead of obsolete locations.
- **DataFrame Column Validation**: Corrected the response validation logic in `_patch_get` to account for implicitly prepended columns. The expected row length is now correctly calculated as `len(requested_columns) + 1` (accounting for the 'Symbol' string injected from the JSON `s` key), fixing `Data length mismatch` errors when constructing the `ScreenerDataFrame`.
- **Dynamic API Pagination (Range)**: Implemented autosizing for the API `range` parameter. When a user supplies an explicit list of tickers, the `range` upper bound now dynamically scales to `len(tickers)` instead of defaulting to a hardcoded `150`, preventing silent truncation of requested universes.
- **Pythonic Filter Operators & Enum Equality**: 
  - Extended magic method monkeypatching (`__gt__`, `__lt__`, etc.) to cover indicator subclasses (`FieldWithInterval`, `FieldWithHistory`), unbreaking the Pythonic filter syntax for multi-timeframe fields.
  - Fixed a critical filter collision bug where `__eq__` and `__ne__` were returning truthy `FieldCondition` objects instead of booleans. This previously caused `StockField.PRICE == StockField.VOLUME` to evaluate as `True`, leading to silent filter overwrites during `Screener._merge_filters()`. The equality logic now strictly compares object identity or `field_name` strings for Enum matching.

Next Steps:
- Apply these robustness principles to future extension patches.
- Continue tracking matrix rerun pipelines using the validated filter engine.

## 2026-04-01: Root Repository Cleanup (SOLID, KISS, DRY, YAGNI)

Goal: Maintain hygiene in the project root by removing defunct pipelines, old markdown tickets, experimental submodules, and artifact configs left over from the structural refactor (shifting from local pipeline implementations towards using `extensions/src/tvscreener_ext/`).

Outcomes:
- Removed legacy development and tooling folders: `.dev/`, `.github/`, `todos/`, `app/`, `semantic/`, `workflows/`.
- Dropped tests targeting deprecated pipeline architectures (`tests/test_analytics_pipeline.py`).
- Kept `extensions/` containing the validated standalone lakehouse persistence and edge analytics logic.
- Kept `tests/unit/` containing standard unit tests targeting the upstream `tvscreener` distribution.

Rationale:
- **YAGNI (You Aren't Gonna Need It)**: Stripped out old notebooks, unmaintained UI app components, deprecated `semantic/` artifacts logic, and defunct github action pipelines. The core system runs completely out of `extensions/` now; there's no need to preserve old iteration remnants in the `feat/forex-strategy-scanner` branch.
- **KISS (Keep It Simple, Stupid)**: Moving forward, repository operations, documentation, and logic should all exist in clearly demarcated boundaries: `docs/`, `extensions/` (pipeline extensions/monkeypatches), and `tests/`.

Next Steps:
- Ensure CI and extension validation runs smoothly without the deleted local dependencies.
- Proceed with scheduled Binance Matrix validation.

## 2026-04-01: Validation Results

Goal: Verify tests and extension logic after root project cleanup.

Outcomes:
- Removed a failing obsolete test (`test_batch_expansion_determinism.py`) which relied on the deleted `workflows/` module.
- Dropped the `StockScreener.set_symbol_types` monkeypatch from `tvscreener_ext/__init__.py` because the upstream version of the library inherently handles SubType mapping perfectly. Doing so fixed 7 failures in `test_filters.py`.
- Fixed JSON datetime serialization inside the local mock of Prefect runner for `test_prefect_runner_smoke.py` by relying on `spec.model_dump(mode='json')` instead of the default `.model_dump()`.
- Successfully ran all 335 unit tests under the extension's environment flag.
- Validation scripts passed `check_upstream_tvscreener_resolution.py`.
- `tvscreener-ext-validate --runner local --matrix` ran the matrix data fetch successfully, evaluating technicals for Forex Majors & Minors, Crypto Base & Perpetuals, and Stock pairs.

Status: Refactoring complete. The application and orchestration are decoupled, running stable, and the test suite is passing securely.

## 2026-04-01: Update Requirements, Specs & Design Docs (SOLID, KISS, DRY, YAGNI)

Goal: Formalize the project root cleanup constraints into the project's specification documents.

Outcomes:
- **`docs/openspec/project.md`**: Appended a new `Repository Layout Constraints (SOLID, KISS, DRY, YAGNI)` section to enforce long-term hygiene and maintainability.
  - **SOLID / YAGNI**: Documented that experimental apps, deprecated scripts, redundant submodules, and obsolete workflows must be systematically removed to prevent dead code accumulation. The repository only contains what is necessary to test and deploy pipeline extensions (`extensions/`, `tests/`, `docs/`).
  - **KISS**: Mandated that all pipeline orchestration, edge analytics, lakehouse storage, and custom screeners must be consolidated into `extensions/src/tvscreener_ext/`.
  - **DRY**: Enforced reliance exclusively on the installed upstream `tvscreener` package. Added instructions to avoid duplicating or over-patching upstream logic when the upstream implementation (e.g., `set_symbol_types` resolution) is sufficient.

Status: Project specifications updated to enforce new structural guarantees moving forward.

## 2026-04-01: Final Root Cleanup & Artifact Pruning

Goal: Complete the project root cleanup by removing shims and build artifacts, and pruning legacy data directories.

Outcomes:
- **Removed `openspec/` shim**: Deleted the redundant root-level `openspec/` directory, as the canonical project context now resides exclusively under `docs/openspec/`.
- **Cleaned `MagicMock/` and `tvscreener.egg-info/`**: Removed accidental test artifacts and built package info to maintain a clean workspace.
- **Pruned legacy `artifacts/`**: Deleted `artifacts/prefect/`, `artifacts/matrix/`, `artifacts/validation/`, and `artifacts/tmp/`. These contained non-contractual legacy logs and debug data from previous iterations. Canonical runs now write to `artifacts/runs/`.
- **Refined `docs/architecture/LAKEHOUSE.md`**: Updated to remove references to the deleted `workflows/` templates and confirmed that batch fan-out is now managed through the `extensions/` distribution.

Status: Root repository is now strictly aligned with SOLID, KISS, and YAGNI principles. All redundant files and legacy data shims have been purged.

## 2026-04-01: Ghost Package Removal & UV Workspace Migration

Goal: Eliminate "ghost" package shadowing and formalize the root as a pure `uv` workspace.

Outcomes:
- **Fixed Package Shadowing**: Modified the root `pyproject.toml` to remove the `[project]` section that incorrectly claimed the root directory was the `tvscreener` package. This prevented a local empty version `0.2.0` from shadowing the real upstream `0.3.0` dependency.
- **`uv` Workspace Formalization**: Converted the repository into a `tool.uv` managed workspace with `package = false`. `tvscreener-ext` is now correctly recognized as a workspace member while `tvscreener` is resolved from the external registry.
- **Dependency Cleanliness**: Ran `uv sync` to purge the ghost package from the virtual environment and ensure all tests run against the true upstream library.
- **Spec Hardening**: Updated `docs/openspec/project.md` to mandate this non-package root structure, ensuring future collaborators don't accidentally re-introduce shadowing.

Status: Repository architecture is now "Zero-Fork" verified at the package manager level. The environment is clean and stable.

## 2026-04-01: Technical Debt Audit & Decomposed Roadmap

Goal: Audit the monolithic `ScreenerController` and define a granular, SRP-compliant refactoring roadmap following SOLID, KISS, DRY, and YAGNI.

Audit Findings:
- **`ScreenerController` (1,615 lines)**: Handles subcommand routing, request normalization, ticker discovery (universes), config generation, execution coordination, edge filtering, and artifact export. This is a severe violation of the Single Responsibility Principle.
- **Tight Coupling**: Universe discovery is tightly coupled to execution, making it difficult to run dry-run audits or mock symbols without triggering full scans.
- **IO Fragmentation**: File exports and metadata handling are scattered across internal methods.

Audited Roadmap (Phased Refactor):
- **Phase 1: Extraction & Decoupling** (Completed)
    - [x] Implement `UniverseResolver` in `tvscreener_ext/services/universe.py`.
    - [x] Implement `ExportService` in `tvscreener_ext/services/export.py`.
    - [x] Update `ScreenerController` to delegate to these new services.
- **Phase 2: Configuration & Logic Pureness** (Completed)
    - [x] Implement `ConfigFactory` in `tvscreener_ext/services/config.py`.
    - [x] Extract `ScanWorkflow` to manage the coordination lifecycle.
    - [x] Extract `ReportingService` to handle audits, reports, and reviews.
    - [x] Update `ScreenerController` to delegate to these services.
- **Phase 3: CLI Hardening** (Completed)
    - [x] Refactor `scan.py` to use a declarative command registry (`argparse` subparsers).
    - [x] Decouple CLI parsing from orchestrator initialization.
    - [x] Remove the remaining legacy methods from `ScreenerController`.

Status: Service-Oriented Refactor complete. The repository is now highly modular, type-safe, and decoupled.

## 2026-04-01: Maintenance Enhancements & Binance Batch Restoration

Goal: Complete the "Cleanup plan (phased)" Task 2 and restore planned Binance batch templates following the root cleanup.

Outcomes:
- **`MaintenanceService`**: Implemented a new service in `tvscreener_ext/services/maintenance.py` to handle artifact lifecycle.
    - **Migration**: Added logic to move legacy artifacts from `artifacts/prefect/` to the canonical `artifacts/runs/` directory.
    - **Pruning**: Added logic to remove artifact directories older than a specified number of days (default 30).
- **CLI Subcommand Hardening**: Updated `tvscreener-ext-scan maintenance` to expose `--migrate-artifacts`, `--prune-artifacts`, and `--prune-days` flags.
- **Binance Batch Templates**: Restored/added the following templates under `extensions/src/tvscreener_ext/prefect/batches/`:
    - `crypto_binance_spot_top100_both.json`
    - `crypto_binance_perp_top100_both.json`
- **Spec Integrity**: Updated `docs/architecture/LAKEHOUSE.md` and `docs/openspec/project.md` to reflect that all orchestration artifacts and templates now reside within the `extensions/` package.

Status: Phased cleanup plan Task 2 is complete. Root repository is fully purged of legacy shims while retaining all planned operational capabilities.

## 2026-04-01: Documentation Refresh & Contract Unification

Goal: Complete the "Cleanup plan (phased)" Task 3 and unify the run discovery contract across all execution modes.

Outcomes:
- **Contract Unification**: Updated `_persist_run_record` in `runner.py` to write a `run_result.json` summary for every execution (including local scans). This establishes a machine-discoverable contract for all runs regardless of the orchestrator.
- **Documentation Parity**:
    - Created **`docs/guide/extensions.md`**: A comprehensive user guide for `tvscreener-ext`, covering CLI usage, maintenance, and programmatic services.
    - Updated **`docs/architecture/LAKEHOUSE.md`**: Formalized `artifacts/runs/` as the canonical artifact store and documented the `run_result.json` discovery contract.
    - Updated **`mkdocs.yml`**: Integrated the new Extensions guide into the project documentation site.
Status: The repository structure is now fully aligned with its documentation, and the migration from legacy `artifacts/prefect/` is officially complete on the write-side.

## 2026-04-01: Final Validation of End-to-End SOA Pipeline

Goal: Verify all architectural updates (Service Decomposition, CLI Hardening, Unified Contract) using full end-to-end scans for Forex and Crypto.

Outcomes:
- **SOA Verification**: Successfully executed 6 major scan categories (Forex Majors/Minors, Crypto Spot Majors/Minors, Crypto Perp Majors/Minors) using the `ScanWorkflow` and its constituent services.
- **Prefect Runner Reliability**: Verified the refactored `run_prefect` and `run_single_spec_flow` in `run_batch.py`. The runner now correctly handles spec normalization and artifact publication.
- **Artifact Contract Validation**: Every validation run successfully produced a machine-discoverable `run_result.json` containing all relevant artifact paths (Matrix, Parquet, Spec).
- **Matrix Integrity**: Confirmed that confluence matrices and technical grading are fully operational under the new service-oriented layout.
- **Status**: The repository is now "Production Ready" for this branch. The orchestration is decoupled, the CLI is hardened, and the data contract is unified.

Next Steps:
- Merge `feat/forex-strategy-scanner` into `main`.
- Final cleanup of temporary validation scripts (`run_validation.py`, `check_runs.py`).


Next Steps:
- Monitor Binance Matrix runs using the new discovery contract.
- Prepare for final release of the service-oriented extensions.

## 2026-04-01: Table Artifact Verification & Multi-Universe Operational Pass

Goal: Verify that Prefect runs correctly publish Table Artifacts for in-browser review, and perform a full operational pass for Forex and Binance universes.

Planned Work:
- Set `TVSCREENER_PUBLISH_TABLE_ARTIFACTS=1` in the verification environment.
- Execute full scan runset using the Prefect runner.
- Verify that `run_result.json` includes `results_table_path`.
- Confirm that `_maybe_publish_prefect_results_table_artifact` path is exercised.

Next Steps:
- Execute `run_validation.py` with table artifacts enabled.
- Verify discovery contract completion.




