## 1. OpenSpec package
- [x] 1.1 Add spec deltas for new capabilities:
  - [x] `specs/multi-asset-pipeline/spec.md`
  - [x] `specs/data-sources/spec.md`
  - [x] `specs/screener-framework/spec.md`
  - [x] `specs/analytics-pipelines/spec.md`
- [x] 1.2 Update repo design docs for alignment:
  - [x] Update `docs/plans/2026-03-02-duckdb-edge-architecture.md` (Iceberg-first reality)
  - [x] Update `docs/plans/2026-03-01-feat-duckdb-mtf-filter-pipeline-plan.md` (edge vs in-flight)
  - [x] Update `docs/brainstorms/2026-03-03-tradingview-scanner-pipeline-scale.md` (bottlenecks + roadmap)

## 2. Follow-up implementation tasks (FR-first reschedule)

### 2A. Functional requirements (execute first)
- [x] 2.1 Add `runs` metadata table (`tvscreener.runs`) and write provenance records per run
- [x] 2.2 Add `code_version` + `params_hash` to run envelope and persist everywhere
- [x] 2.3 Add a `DataSource` adapter interface and implement at least:
  - [x] TradingView adapter (current)
  - [x] Stub adapter for “broker/exchange” with the same output contract
- [x] 2.4 Add a screener registry + composition primitives (ranker + filters + strategy)
- [x] 2.5 Add long-form table option (timeframe as a column) + materialized “matrix-ready” outputs

### 2B. Non-functional requirements (execute after 2A)
- [ ] 2.6 Add per-source performance baselines (ingest throughput + analytics latency)
- [ ] 2.7 Add compaction/snapshot-expiration maintenance policy for Iceberg tables
- [ ] 2.8 Add richer run observability dashboards (coverage trends, failure classes)

## 4. Orchestration scale plan (next)
- [x] 4.1 Add “batch spec” generation:
  - generate `PipelineRunSpec[]` from a higher-level batch definition:
    - asset types (forex/stock/crypto/…)
    - universes or symbol shards
    - timeframe sets (multiple `timeframe_set_id`)
    - scanner families (opportunity/strategy)
- [x] 4.2 Prefect mapping/fan-out:
  - execute batch specs with concurrency controls
  - use `params_hash` for idempotent run IDs
  - persist artifacts under `artifacts/prefect/<params_hash>/`
- [x] 4.2.1 Universe sharding (pairs chunks) for fan-out parallelism
- [x] 4.3 Add upstream rate-limit policy per source (TradingView):
  - per-worker throttling
  - exponential backoff + jitter around fetch steps
  - bounded retries for fetch-only steps (not analytics)

## 6. Rescheduled next tasks (execution queue)
- [x] 6.1 Complete 2.1 and 2.2 (run metadata + reproducibility envelope)
- [x] 6.2 Complete 2.3 (multi-source adapter baseline)
- [x] 6.3 Complete 4.3 (source-aware throttling/retry for stable fan-out)
- [x] 6.4 Complete 2.4 (registry + screener/scanner composition)
- [x] 6.5 Complete 2.5 (long-form + product outputs for multi-timeframe scale)
- [x] 6.6 Run section 3 verification smoke tests across forex + stock + crypto

## 5. TradingView scan batching reliability
- [x] 5.1 Ensure `/scan` tickers batching is not truncated by default `range=[0,150]`:
  - auto-size range to `[0,len(tickers)]` when tickers are provided and range is not explicitly overridden

## 3. Verification plan (once implemented)
- [x] 3.1 Multi-asset scan smoke: run forex + stock + crypto and confirm:
  - [x] `entity_id` populated
  - [x] overwrite scoping does not delete unrelated entities
  - [x] per-source coverage gating blocks partial Silver/Gold
- [x] 3.2 Edge analytics smoke:
  - [x] DuckDB SQL works on Iceberg identifiers without local snapshot files
  - [x] Narwhals pipeline transforms work over Iceberg-backed relations
- [x] 3.3 Fan-out determinism and timeframe contract smoke:
  - [x] same matrix batch definition produces stable run `params_hash` set/order
  - [x] expanded specs include non-null `timeframe_set_id`
  - [x] scanner family/pipeline contract is consistent across asset types and timeframe sets

## 7. Current status review and next focus
- [x] 7.1 FR baseline status reviewed (FR-1..FR-5 complete)
- [x] 7.2 Verification status reviewed (3.1..3.3 complete)
- [ ] 7.3 Begin deferred NFR execution with FR regression gates:
  - [ ] 2.6 performance baselines
  - [ ] 2.7 maintenance policy
  - [ ] 2.8 observability dashboards

## 8. Prefect orchestration readiness for scale
- [x] 8.1 Review orchestration default posture and transition criteria
- [x] 8.2 Execute Prefect rerun audits for scalable universes:
  - [x] majors/minors rerun (`both`)
  - [x] all-universe sharded rerun
  - [x] analytics-only replay read-only verification
- [x] 8.3 Complete Prefect artifact audit backlog (`add-prefect-runner-wrapper` tasks `9.1`..`9.5`)
- [x] 8.4 Switch scanner default runner to Prefect with local fallback and post-flip smoke

## 9. Asset expansion readiness audit (commodities, crypto, equities)
- [x] 9.1 Build asset readiness matrix:
  - [x] identity and schema readiness (`asset_type`, `entity_id`, overwrite safety)
  - [x] source adapter and coverage readiness by asset type
  - [x] screener parity readiness (composition + output contracts)
- [x] 9.2 Run targeted smoke/rerun checks per asset family under Prefect (via code-path audit + existing rerun evidence)
- [x] 9.3 Classify each asset family: `ready`, `ready-with-gaps`, `blocked`
- [ ] 9.4 Convert gaps into prioritized implementation tasks with owners
  - [ ] 9.4.1 Strategy scanner parity for non-forex assets
  - [ ] 9.4.2 Asset-specific universe selector model (non-forex semantics)
  - [ ] 9.4.3 Non-forex ticker normalization/validation before fetch

## 10. Rescheduled preparation queue (execute before new NFR work)
- [ ] 10.1 Prep Phase A: strategy parity foundations
  - [ ] deliver non-forex strategy scanner parity
  - [ ] remove forex-only strategy assumptions from output contracts
- [ ] 10.2 Prep Phase B: asset-aware selector semantics
  - [ ] implement per-asset universe selector contract
  - [ ] keep compatibility aliases and explicit normalization
- [ ] 10.3 Prep Phase C: ingestion safety for new assets
  - [ ] implement non-forex ticker normalization/validation pre-fetch
  - [ ] add readiness checks for commodity/equity ticker conventions
- [ ] 10.4 Prep Phase D: readiness reclassification run
  - [ ] rerun Prefect smoke matrix across equities/crypto/commodities
  - [ ] update readiness labels and convert residual gaps into tracked work
