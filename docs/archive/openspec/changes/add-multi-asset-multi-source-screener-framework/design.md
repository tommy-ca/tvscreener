# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Context (current architecture)
`tvscreener` runs scanners (opportunity/strategy) against TradingView endpoints, transforms results,
and persists medallion outputs to an Iceberg lakehouse:

- **Bronze**: raw-ish ingestion (append)
- **Silver**: standardized columns + canonical identity (overwrite scoped)
- **Gold**: scored/features for serving (overwrite scoped) + `signals_latest` convenience table

Edge analytics use **DuckDB** (`EdgeQueryClient`) to run SQL against Iceberg identifiers by loading
Iceberg scans into Arrow (extensions disabled by hardening). Narwhals is used for backend-agnostic
transforms and pipelines that interleave SQL and expressions.

## Goals / Non-Goals

### Goals
- Make the system **multi-asset by construction**: keys, partitions, overwrite scope, and universes
  work without forex-specific assumptions (`PAIR`).
- Make the system **multi-timeframe by construction**: variable timeframe sets do not cause schema
  churn or correctness issues, and cross-timeframe analytics have explicit contracts.
- Add a **data source adapter contract** so we can ingest from multiple upstreams while keeping a
  stable medallion interface.
- Make screeners composable: **ranking**, **filters**, and **strategy-specific** logic should be
  pluggable and reusable across asset types and sources.
- Improve performance + operability by naming bottlenecks and defining mitigations.

### Non-Goals
- Implementing all new data sources in this change (we are specifying the framework).
- Migrating medallion tables to long-form immediately (we will define a phased path).
- Introducing a workflow engine (Airflow/DBOS) right now (but the design must not block it later).

## FR-first delivery strategy

This design follows a strict execution rule: complete functional requirements first, then optimize
non-functional concerns. The target is a usable and correct multi-asset, multi-timeframe
screener/scanner that can scale by composition.

### FR priority order
1. Multi-asset identity + overwrite correctness
2. Multi-timeframe run envelope and analytics contract
3. Multi-source adapter + coverage gating
4. Screener/scanner composition and deterministic fan-out
5. Analytics product table consistency (`signals_latest`, `signals_batch`)

### NFR deferral policy
- Performance and cost tuning is deferred unless it blocks FR correctness.
- Additional orchestration backends are deferred unless needed for FR delivery.
- Deep observability/reporting is deferred until FR acceptance criteria are met.

## Bottleneck review (what will hurt first)

### 1) Upstream API throughput and partial runs
- **Cause**: rate limits/timeouts and retry storms.
- **Symptoms**: missing symbols, inconsistent counts, silent partial ingestion.
- **Mitigations**:
  - explicit coverage metrics per run (requested/returned/failed batches)
  - publish gating: Bronze may append partial; Silver/Gold must not publish under threshold
  - per-source backoff/jitter and concurrency controls

### 2) Lakehouse write amplification (small files + schema evolution overhead)
- **Cause**: overwriting many partitions often; calling schema union on each write.
- **Symptoms**: slow scans, many small data files, long metadata operations.
- **Mitigations**:
  - batch writes (single Arrow table per stage, per scan unit)
  - periodic compaction + snapshot expiration
  - avoid per-write schema union when schema is stable (predefined schema or “evolve only on change”)

### 3) Query scalability (Arrow materialization)
- **Cause**: reading an Iceberg table into Arrow before DuckDB can query it.
- **Symptoms**: high memory use, slow “audit” queries as history grows.
- **Mitigations**:
  - ensure partition pruning is used (query patterns always filter on partition columns)
  - keep small “product tables” for common access (`signals_latest`, `signals_batch`)
  - for large tables, prefer time-windowed scans (latest `signal_date` / `ingest_date`) before Arrow

### 4) Wide-schema timeframe expansion
- **Cause**: adding timeframes increases column count (`TREND_15`, `TREND_60`, ...).
- **Symptoms**: schema churn, hard to support variable timeframe sets.
- **Mitigations**:
  - Phase A (now): keep wide, stabilize identity + envelope + overwrite scope
  - Phase B (next): introduce long-form tables with `timeframe` as a column and “factor_name/value”
  - Phase C (optional): derived wide views/materializations for UX (matrix rendering) only

## Data pipelines vs analytics pipelines (hard separation)

### Data pipelines (canonical)
Data pipelines SHALL:
- ingest upstream data
- standardize schemas + identity
- compute reusable features
- persist outputs to Iceberg tables (Bronze/Silver/Gold)

Data pipelines SHALL NOT:
- depend on a specific analytics query engine
- mutate “latest” or “report” tables as a side effect of ingestion unless explicitly modeled as an
  analytics product

### Analytics pipelines (pluggable backends)
Analytics pipelines SHALL:
- consume Iceberg-backed tables (by identifier + optional snapshot selector)
- produce analytics products such as:
  - `signals_latest` (latest-per-entity)
  - `signals_batch` (matrix-ready aggregates per run/date)
  - ranked reports and strategy-specific outputs

Analytics pipelines SHOULD be backend-agnostic:
- DuckDB is the default “edge OLAP” backend today
- other backends (Polars lazy, Spark, Trino, etc.) can be introduced later behind the same contract

## Multi-timeframe as a first-class dimension

### Decision: timeframe identity has two layers
- `timeframe_set_id`: identifies the *set* of timeframes used for a run/unit (fan-out/fan-in key)
- `timeframe`: identifies an individual timeframe (required for long-form storage and PIT analytics)

### Decision: wide vs long is a storage choice, not an API choice
- Phase A: wide rows (timeframe-as-columns) are acceptable short-term for UX and small universes.
- Phase B: long-form medallion tables become the canonical representation for variable timeframe sets.
- Phase C: materialize wide “matrix views” from long-form features as analytics products.

## Analytics backend contract (design sketch)

Define a minimal contract so analytics pipelines can swap query backends without changing the
pipeline logic:

- **Input**: `(table_id, snapshot_id?, predicates?, limit?)`
- **Operations**:
  - `sql(query, params?)`
  - `transform(expr_fn)` (Narwhals expressions)
  - `collect()` / `to_arrow()` / `to_pandas()` depending on consumer

Current implementation maps this to:
- `EdgeQueryClient` (DuckDB) + `AnalyticsPipeline` (SQL + Narwhals)

## Key design decisions (multi-asset + multi-source)

### Decision: Dataset taxonomy first
Do not force different grains into one table. Define dataset types and keep boundaries:
- `screener_snapshot` (TradingView-like observations)
- `market_klines` (OHLCV bars)
- `market_ticks` (ticks/quotes)
- `market_orderbook` (L2 snapshots/deltas)

### Decision: Run envelope is required everywhere
Every persisted stage row SHALL carry:
- `run_id`, `fetched_at_utc`, `asset_type`, `timeframes`, `timeframe_set_id`
- `source` and `scanner_family` (when relevant)
- `code_version` and `params_hash` (for reproducibility)

Also define a `runs` metadata table that records:
- request params + resolved universe membership snapshot
- Iceberg snapshot IDs produced for each stage

### Decision: Canonical identity is the join key
Use:
- `entity_id` (stable, preferably `{venue}:{symbol}`)
- `symbol` (symbol-only)
- `venue` (exchange/broker)
Keep asset-specific convenience columns but do not depend on them for correctness.

### Decision: Screeners are composable programs
Model a screener as:
1) **Source selection** (which upstreams, and how to reconcile)
2) **Universe selection** (entity set)
3) **Feature computation** (data pipeline: medallion)
4) **Analytics** (analytics pipeline: ranking, strategy logic, filter predicates; backend-agnostic)
5) **Presentation** (matrix/detailed/export)

## Phased roadmap (how we get there)

### Phase 0 (now): doc/spec alignment
- Update outdated design docs to match Iceberg-first reality.
- Add OpenSpec requirements for multi-source and multi-screener composition.

### Phase 1: multi-asset correctness hardening
- Ensure `scanner_family` is correct across all scanner types.
- Ensure `entity_id` is always set when a per-asset identifier exists (`PAIR` for forex fallback).
- Ensure overwrite scoping uses `entity_id` + partition keys.

Acceptance target:
- same-run writes for one asset universe do not mutate unrelated entities or asset types.

### Phase 2: multi-source adapters
- Introduce `DataSource` adapter interface and per-source coverage/health gating.
- Add `source` + `source_event_id` (where applicable) to Bronze.
- Add source-aware fetch throttling and bounded retries (`min_interval`, `jitter`,
  exponential backoff with max attempts) for ingestion-only steps.

Acceptance target:
- adding a second source does not require changing medallion or analytics core contracts.

### Phase 3: multi-screener framework
- Introduce a registry for screener families (ranking, filters, strategy-specific).
- Enable composition: “rank then filter then strategy confirm” pipelines.

Acceptance target:
- a single batch definition can fan out across multiple asset types and timeframe sets with
  deterministic run envelopes.

### Phase 4: long-form (optional) + product tables
- Add long-form tables to handle variable timeframe sets.
- Add materialized “product tables” for UX (`signals_batch`, `signals_latest`).
- Add configurable long-form materialization (`signals_long`) from wide Gold rows using
  `timeframe` as a first-class dimension.

Acceptance target:
- matrix/scanner outputs are generated from analytics product tables, not ad-hoc files.

## Rescheduled next execution plan

Execution order is intentionally updated to maximize FR throughput:
1. Phase 1 (multi-asset correctness hardening)
2. Phase 2 (multi-source adapters)
3. Phase 3 (multi-screener composition)
4. Product-table consistency checks from Phase 4
5. Deferred NFR tuning and platform hardening

## Verification execution (FR checkpoint)

Section 3 verification smoke is executed with deterministic local tests plus CLI query smoke:
- multi-asset contract smoke (forex/stock/crypto):
  - canonical identity population (`entity_id`)
  - overwrite scope includes `asset_type` and `entity_id`
  - coverage gating blocks partial Silver/Gold publish
- deterministic fan-out + timeframe contract smoke:
  - identical matrix batch specs expand to stable `params_hash` set/order
  - expanded specs include non-null `timeframe_set_id`
  - scanner family/pipeline contract remains consistent across asset types/timeframe sets
- analytics smoke:
  - DuckDB query on Iceberg identifier (`tvscreener.signals_latest`) via CLI
  - Narwhals transform pipeline execution via analytics tests

## Current status and next phase

Current status review:
- FR baseline is complete for this change scope (Phases 1-4 baseline outcomes delivered)
- FR verification checkpoints are green (identity/overwrite safety, fan-out determinism,
  product-table outputs)

Next phase:
- Execute deferred NFR work (performance baselines, maintenance policy, observability)
- Keep FR-first guardrails: every NFR step must pass FR regression checks before acceptance

## Orchestration default posture (Prefect)

For scalable multi-asset, multi-timeframe execution, workflow orchestration SHOULD default to Prefect
once readiness gates are complete.

Readiness focus:
- analytics-only read-only safety verified in practice
- deterministic artifacts and machine-consumable contracts audited
- rerun reliability validated for both targeted and sharded universe batches

Readiness gates are now passed; Prefect is the default orchestration path.
Local runner remains explicit fallback for debug/recovery paths.

Operational defaults are aligned to simplify CLI workflow runs:
- Prefect runtime defaults are provided via `.env` template (`PREFECT_HOME`, startup timeout)
- scanner settings defaults are aligned for predictable baseline runs (`majors`, `240,60,15`)

## Expansion readiness audit (next)

Before broadening production scope to additional asset families (commodities, cryptocurrencies,
equities), run a structured readiness audit.

### Audit dimensions
1. **Identity and schema**
   - `entity_id` quality and stability by asset type
   - overwrite-scope safety in mixed-asset partitions
2. **Source coverage and ingestion reliability**
   - source coverage matrix per asset type
   - rate-limit/retry behavior and coverage-gating outcomes
3. **Screener and analytics parity**
   - parity of composition steps (`rank -> filter -> strategy`) per asset family
   - matrix/output contract parity (`signals_latest`, `signals_batch`, optional `signals_long`)
4. **Orchestration and rerun operability**
   - deterministic fan-out and shard behavior under Prefect
   - idempotent rerun semantics and artifact discoverability

### Audit outcomes
- Each asset type is labeled: `ready`, `ready-with-gaps`, or `blocked`.
- Gaps must map to explicit tracked tasks before production expansion.

### Current audit result (code-level review)

#### Equities (`stock`)
- **Status**: `ready-with-gaps`
- **Evidence**:
  - generic opportunity pipeline path exists via `AssetScreenerFactory` (`stock` mapping)
  - universe and fan-out support exists in orchestrator (`UNIVERSE_MAP`, Prefect matrix expansion)
- **Gaps**:
  - strategy path is still forex-coupled (`ForexStrategyScanner` used regardless of asset type)
  - universe selector semantics are forex-oriented (`majors`/`minors`) and not asset-specific

#### Cryptocurrencies (`crypto`)
- **Status**: `ready-with-gaps`
- **Evidence**:
  - generic opportunity path exists (`crypto` mapping in factory + universe constants)
  - run envelope, medallion contract, and Prefect orchestration are asset-agnostic
- **Gaps**:
  - strategy parity gap same as equities (forex-coupled strategy scanner)
  - source-readiness audit still needed for exchange/ticker normalization at scale

#### Commodities (`commodity`/`futures`)
- **Status**: `blocked`
- **Evidence**:
  - asset alias normalization and futures screener mappings exist
- **Blocking gaps**:
  - no commodity-specific strategy parity (still forex-coupled strategy scanner)
  - ticker/universe normalization requires explicit validation for commodity symbols prior to
    production-scale ingestion

### Priority gaps to close
1. Decouple strategy scanner from forex-specific assumptions (`PAIR`, naming, config semantics).
2. Introduce asset-specific universe selectors (replace forex-only selector semantics in CLI contracts).
3. Add per-asset ticker normalization/validation layer for non-forex universes before fetch.

## Rescheduled execution plan (multi-asset preparation)

This plan supersedes the immediate NFR-first queue and prepares the platform for broader
multi-asset, multi-timeframe rollout.

### Prep Phase A: parity foundations
1. Implement strategy scanner parity for non-forex assets.
2. Remove forex-only assumptions from strategy analytics joins and rendering contracts.

### Prep Phase B: asset-aware selection semantics
1. Replace forex-centric universe selectors with asset-aware selectors.
2. Keep backwards-compatible aliases where possible, but normalize to per-asset contract.

### Prep Phase C: ingestion safety for new assets
1. Add non-forex ticker normalization/validation before source fetch.
2. Add explicit coverage/readiness checks for commodity and equity symbol conventions.

### Prep Phase D: readiness reclassification
1. Re-run Prefect smoke/rerun matrix for commodities, crypto, and equities.
2. Reclassify each asset family (`ready`, `ready-with-gaps`, `blocked`).

### Deferred after prep phases
- Resume NFR queue (performance baselines, maintenance policy, observability) with FR + prep regression gates.
