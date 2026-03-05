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

## 2. Follow-up implementation tasks (not in this doc-only change)
- [ ] 2.1 Add `runs` metadata table (`tvscreener.runs`) and write provenance records per run
- [ ] 2.2 Add `code_version` + `params_hash` to run envelope and persist everywhere
- [ ] 2.3 Add a `DataSource` adapter interface and implement at least:
  - [ ] TradingView adapter (current)
  - [ ] Stub adapter for “broker/exchange” with the same output contract
- [ ] 2.4 Add a screener registry + composition primitives (ranker + filters + strategy)
- [ ] 2.5 Add long-form table option (timeframe as a column) + materialized “matrix-ready” outputs

## 3. Verification plan (once implemented)
- [ ] 3.1 Multi-asset scan smoke: run forex + stock + crypto and confirm:
  - [ ] `entity_id` populated
  - [ ] overwrite scoping does not delete unrelated entities
  - [ ] per-source coverage gating blocks partial Silver/Gold
- [ ] 3.2 Edge analytics smoke:
  - [ ] DuckDB SQL works on Iceberg identifiers without local snapshot files
  - [ ] Narwhals pipeline transforms work over Iceberg-backed relations

