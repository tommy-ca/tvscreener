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

### Phase 2: multi-source adapters
- Introduce `DataSource` adapter interface and per-source coverage/health gating.
- Add `source` + `source_event_id` (where applicable) to Bronze.

### Phase 3: multi-screener framework
- Introduce a registry for screener families (ranking, filters, strategy-specific).
- Enable composition: “rank then filter then strategy confirm” pipelines.

### Phase 4: long-form (optional) + product tables
- Add long-form tables to handle variable timeframe sets.
- Add materialized “product tables” for UX (`signals_batch`, `signals_latest`).

