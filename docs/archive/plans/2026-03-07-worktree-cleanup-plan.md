# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Plan: FR-first scalable multi-asset multi-timeframe screener/scanner

This plan supersedes the previous runner-focused checklist for execution prioritization.
Goal: ship functional scalability first for a multi-asset, multi-timeframe screener/scanner baseline.

### Guiding rule
- Prioritize FRs over NFRs until FR acceptance criteria pass.
- Defer optimization/hardening work unless it blocks FR correctness.

### Source of truth updated
- Proposal: `docs/openspec/changes/add-multi-asset-multi-source-screener-framework/proposal.md`
- Design: `docs/openspec/changes/add-multi-asset-multi-source-screener-framework/design.md`
- Tasks: `docs/openspec/changes/add-multi-asset-multi-source-screener-framework/tasks.md`
- Specs:
  - `docs/openspec/changes/add-multi-asset-multi-source-screener-framework/specs/multi-asset-pipeline/spec.md`
  - `docs/openspec/changes/add-multi-asset-multi-source-screener-framework/specs/data-sources/spec.md`
  - `docs/openspec/changes/add-multi-asset-multi-source-screener-framework/specs/screener-framework/spec.md`
  - `docs/openspec/changes/add-multi-asset-multi-source-screener-framework/specs/analytics-pipelines/spec.md`

### FR backlog (must ship first)
- [x] FR-1 Multi-asset correctness:
  - enforce canonical identity (`asset_type`, `entity_id`) and safe overwrite scope
- [x] FR-2 Multi-timeframe correctness:
  - enforce stable `timeframe_set_id` and deterministic fan-out/run envelopes
- [x] FR-3 Multi-source ingestion contract:
  - implement `DataSource` adapter baseline + source provenance fields
- [x] FR-4 Screener/scanner composition:
  - implement registry + composable `rank -> filter -> strategy` flow
- [x] FR-5 Analytics product consistency:
  - produce stable `signals_latest` and `signals_batch` contracts across families/assets

### Rescheduled next tasks (execution order)
- [x] 1) Implement `tvscreener.runs` metadata + persist `code_version`/`params_hash`
- [x] 2) Implement source adapter baseline (TradingView + stub secondary source)
- [x] 3) Add per-source throttling/retry policy for fan-out stability
- [x] 4) Implement screener/scanner registry and composition primitives
- [x] 5) Add long-form timeframe option and matrix-ready product outputs
- [x] 6) Run verification smoke for forex + stock + crypto across multiple timeframe sets

### FR acceptance checkpoints
- [x] Deterministic expansion of batch definitions by `asset_type x universe_shard x timeframe_set_id x scanner_family`
- [x] No cross-asset or cross-entity data loss from overwrite operations
- [x] Same screening program executes across asset types/timeframe sets without contract forks
- [x] Matrix/scanner outputs are generated from analytics product tables (not ad-hoc artifacts)

### Current status review
- FR baseline is complete for the multi-asset, multi-timeframe screener/scanner scope.
- OpenSpec verification items (`3.1`, `3.2`, `3.3`) are complete.
- Next work phase is NFR-only, with FR regression gates required on every NFR change.

### Next execution queue (post-FR)
- [ ] 7) NFR-1: establish per-source performance baselines (ingest throughput + analytics latency)
- [ ] 8) NFR-2: define and validate compaction/snapshot-expiration maintenance policy
- [ ] 9) NFR-3: add run observability dashboards (coverage trends, failure classes)
- [ ] 10) Add FR regression gate suite to NFR workflow entry criteria

### Expansion readiness audit (next planning track)
- [x] 19) Build readiness matrix for commodities/crypto/equities
- [x] 20) Audit identity + overwrite safety per asset family
- [x] 21) Audit source coverage/retry/rate-limit posture per asset family
- [x] 22) Audit screener parity + matrix output contracts per asset family
- [x] 23) Classify readiness (`ready`/`ready-with-gaps`/`blocked`) and open gap tasks

### Expansion readiness results
- Equities (`stock`): `ready-with-gaps`
- Cryptocurrencies (`crypto`): `ready-with-gaps`
- Commodities (`commodity`/`futures`): `blocked`

### Expansion gap queue (post-audit)
- [ ] 24) Implement strategy scanner parity for non-forex assets
- [ ] 25) Implement asset-specific universe selector semantics
- [ ] 26) Add non-forex ticker normalization/validation before fetch

### Rescheduled preparation queue (current priority)
- [ ] 27) Prep A: complete non-forex strategy parity
- [ ] 28) Prep B: implement asset-aware universe selector model
- [ ] 29) Prep C: implement non-forex ticker normalization/validation guardrails
- [ ] 30) Prep D: rerun Prefect readiness matrix and reclassify assets
- [ ] 31) Resume NFR queue only after 27-30 are green

### Prefect default transition (review + audit)
- **Current default**: CLI scanner runner is `prefect` (`tvscreener/cli.py`).
- **Target default**: scanner runner defaults to `prefect`, with explicit `--runner local` fallback.
- **Readiness status**: **ready and switched**.
  - Completed:
    - analytics-only read-only audit passed
    - artifact audit items `9.1`..`9.5` completed
    - FR regression and fan-out contract tests remain green after Prefect reruns
  - Remaining improvements (non-blocking):
    - workflow quality items `7.2` and `7.3` for better scale operability

### Prefect rerun plan (next)
- [x] 11) Run Prefect majors/minors rerun (`both`) and capture artifacts + summary
- [x] 12) Run Prefect all-universe sharded rerun and validate shard completeness
- [x] 13) Run Prefect analytics-only replay and verify product-table read-only invariants
- [x] 14) Complete artifact audit checklist (`9.1`..`9.5`)
- [x] 15) Flip CLI default runner to `prefect` and execute post-flip smoke

### Default config simplification
- [x] 16) Align scanner settings defaults for simple CLI runs (`majors`, `240,60,15`)
- [x] 17) Update `.env.example` with Prefect runtime best defaults
- [x] 18) Add unit test coverage for implicit Prefect default runner behavior

### Progress notes
- 2026-03-07: completed run metadata baseline for FR queue item 1.
  - `LocalRunner` now appends run records to `tvscreener.runs`.
  - persisted medallion rows now include `params_hash` and `code_version` from run context.
  - focused tests added and passing:
    - `tests/unit/test_pipeline_runner.py`
    - `tests/unit/test_base_medallion.py`
- 2026-03-07: completed source adapter baseline for FR queue item 2.
  - Added adapter contract + implementations:
    - `tvscreener/lib/data_sources.py` (`TradingViewDataSource`, `StubDataSource`)
  - Wired adapter selection into opportunity ingestion via `extra_options.data_source`.
  - Added source provenance propagation (`source`, `source_event_id`) across persisted stages.
  - focused tests added and passing:
    - `tests/unit/test_data_sources.py`
- 2026-03-07: completed source-aware throttling/retry for FR queue item 3.
  - Added source policy controls for ingestion fetch steps (`source_policies`):
    - `min_interval_seconds`, `jitter_seconds`
    - `fetch_max_retries`, `fetch_retry_base_seconds`, `fetch_retry_max_seconds`
  - Implemented bounded exponential backoff retries in fetch batching path only.
  - Added ingest stats emission for full-failure batches (coverage=0, failed_batches tracked).
  - focused tests added and passing:
    - `tests/unit/test_base_medallion.py`
- 2026-03-07: completed screener/scanner registry + composition primitives for FR queue item 4.
  - Added family registry and composable data stages (`rank_by`, `filter_expr`, `strategy_is`).
  - Wired `ScreenerController.run_scan` through the registry contract.
  - focused tests added and passing:
    - `tests/unit/test_screener_registry.py`
    - `tests/unit/test_cli_filters.py`
- 2026-03-07: completed long-form + matrix-ready product output baseline for FR queue item 5.
  - Materialized `tvscreener.signals_batch` on Gold persistence.
  - Added optional long-form materialization (`extra_options.long_form_output`) to `tvscreener.signals_long`.
  - focused tests added and passing:
    - `tests/unit/test_base_medallion.py`
- 2026-03-07: completed multi-asset/multi-timeframe verification smoke for FR queue item 6.
  - Added deterministic smoke tests for section 3.1:
    - `tests/unit/test_multi_asset_smoke.py`
      - multi-asset `entity_id` population (forex/stock/crypto)
      - overwrite scope includes `asset_type` + `entity_id`
      - coverage gating blocks Silver publish on partial ingest
  - Ran analytics transform smoke:
    - `tests/test_analytics_pipeline.py`
  - Ran direct Iceberg identifier query smoke via CLI:
    - `uv run python -m tvscreener.cli query tvscreener.signals_latest --sql "SELECT * FROM df LIMIT 1" --head 1`
- 2026-03-07: completed FR-1/FR-2 acceptance closure.
  - Added deterministic fan-out tests:
    - `tests/unit/test_batch_expansion_determinism.py`
      - stable `params_hash` ordering for identical matrix batches
      - multi-asset + multi-timeframe contract with non-null `timeframe_set_id`
  - Reconfirmed overwrite-scope and identity safety:
    - `tests/unit/test_multi_asset_smoke.py`
- 2026-03-07: completed readiness review for Prefect-default transition.
  - audited current default runner posture (`local`) and Prefect workflow baseline
  - documented blockers and transition gates in OpenSpec docs + this plan
- 2026-03-07: executed Prefect reruns and completed default-runner transition.
  - Prefect batch reruns completed:
    - `workflows/prefect/batches/forex_majors_minors_both.json` (`count=6`, success)
    - `workflows/prefect/batches/forex_all_refresh.json` (`count=6`, success)
    - `workflows/prefect/batches/forex_all_analytics.json` (`count=2`, success)
  - analytics-only read-only invariant verified on `tvscreener.signals_latest`:
    - before max(`fetched_at_utc`): `2026-03-07 09:01:18.057433`
    - after  max(`fetched_at_utc`): `2026-03-07 09:01:18.057433`
  - idempotent rerun validated:
    - `--skip-existing` returns per-run `skipped` flags for data/analytics/both
  - switched scanner CLI default runner to Prefect:
    - `tvscreener/cli.py` `--runner` default changed to `prefect`
  - post-flip smoke passed:
    - implicit default Prefect run (`tvscreener-scan` without `--runner`)
    - explicit local fallback run (`--runner local`)
- 2026-03-07: simplified default scanner workflow configuration.
  - aligned settings default universe to `majors` in `tvscreener/config/settings.py`
  - updated `.env.example` with Prefect runtime defaults (`PREFECT_HOME`, startup timeout)
  - confirmed CLI default runner behavior with unit coverage in `tests/unit/test_cli_filters.py`
- 2026-03-07: completed asset expansion readiness audit (commodities/crypto/equities).
  - equities classified `ready-with-gaps`
  - cryptocurrencies classified `ready-with-gaps`
  - commodities classified `blocked`
  - logged prioritized gap queue for strategy parity, universe semantics, and ticker normalization
- 2026-03-07: rescheduled roadmap for multi-asset preparation.
  - moved execution priority to preparation phases A-D before additional NFR work
  - updated requirements/spec/design/tasks and this plan to reflect the new sequence
- 2026-03-07: planned expansion readiness audit for additional asset families.
  - updated requirements/spec/design docs with explicit audit contracts
  - added tracked tasks for commodities, cryptocurrencies, and equities readiness classification

### NFR backlog (deferred until FR complete)
- [ ] Performance/cost tuning (compaction cadence, Arrow materialization tuning)
- [ ] Extended observability dashboards and SLO reporting
- [ ] Additional orchestration/query backend hardening beyond current baseline
