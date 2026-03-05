---
title: Multi-Asset Iceberg Catalog + Medallion Table Design
date: 2026-03-03
status: draft
---

# Multi-Asset Iceberg Catalog + Medallion Table Design

## Goals

- Split **data pipelines** (ingestion, normalization, feature engineering) from **analytics pipelines** (batch queries, realtime signals, rendering/export).
- Extend the lakehouse to support **multiple asset types** and **variable timeframe sets** without overwriting each other.
- Treat “universe” as a tradable asset group (an input selector), not a storage design axis.
- Make every run traceable via `run_id` + `fetched_at_utc` and provable via Iceberg `snapshot_id`.
- Keep TradingView screener snapshots as one dataset type, while making room for additional market data types (klines, ticks, orderbooks) with clear table boundaries.

## Multi-timeframe-first principle (scope driver)

Multi-timeframe is not an “extra feature”; it is the core scaling axis that determines table shape,
analytics patterns, and query backend choices.

Principles:

- Treat `timeframe_set_id` as a **first-class key** for all wide-form outputs (prevents collisions).
- Plan for **long-form** medallion tables where `timeframe` is an explicit column, enabling:
  - variable timeframe sets without schema churn
  - point-in-time (PIT) analytics and per-timeframe audits
- Treat “matrix view” as an **analytics product** (a rollup across timeframes), not a storage grain.

## Current implementation status (as of branch HEAD)

This section captures what is already implemented in code so readers can distinguish “now” vs “proposed”.

- **Catalog**: local SQL (SQLite) catalog + local warehouse are provisioned by code (see `tvscreener/lib/lakehouse/manager.py`).
- **Run envelope (partial)**:
  - Implemented: `run_id`, `fetched_at_utc`, `asset_type`, `timeframes`, `timeframe_set_id`, `source`
  - Gap: `scanner_family` is not yet consistently correct across scanner types; `code_version` and `params_hash` are not yet recorded.
- **Canonical identity (partial)**:
  - Implemented in Silver standardization: `venue`, `symbol`, `entity_id` derived from `Symbol` (or best available source column).
  - Gap: some downstream logic still relies on asset-specific columns like `PAIR` for joins/filters.
- **Partitioning**: identity-partitioning includes `asset_type` and `timeframe_set_id` to prevent cross-asset/timeframe collisions.
- **Overwrite safety (improved)**: overwrite scoping prefers `entity_id` when present, falling back to asset-specific keys as needed.
- **Analytics output (partial)**: a fast `tvscreener.signals_latest` table exists; the plan proposes `signals_batch`/`signals_realtime` as explicit analytics outputs.

## Current State Audit

### Iceberg catalog

- Local SQLite catalog at `~/.tvscreener/lakehouse/catalog.db` and local warehouse at `~/.tvscreener/lakehouse/warehouse`.
- Catalog configuration is now configurable via layered Pydantic settings (YAML/ENV) and is consumed by `tvscreener/lib/lakehouse/manager.py`.

#### Configuration (YAML + ENV layered)

YAML (`tvscreener.yaml`) example:

```yaml
lakehouse:
  catalog:
    mode: local            # local | remote
    name: local
    type: sql
    # remote:
    #   uri: "postgresql+psycopg://user:pass@host:5432/iceberg"
    #   warehouse: "s3://bucket/warehouse"
    properties: {}
```

ENV example (uses `TVSCREENER_` prefix + nested delimiter `_`):

```bash
export TVSCREENER_LAKEHOUSE_CATALOG_MODE=remote
export TVSCREENER_LAKEHOUSE_CATALOG_REMOTE_URI="postgresql+psycopg://user:pass@host:5432/iceberg"
export TVSCREENER_LAKEHOUSE_CATALOG_REMOTE_WAREHOUSE="s3://bucket/warehouse"
```

**Risks:**

- SQLite catalog lock contention for concurrent writers.
- Hard to share a single catalog across machines/processes (especially once workflows become durable/queued).

### Medallion tables

- `tvscreener.bronze` is identity-partitioned by `asset_type`, `ingest_date`, and `timeframe_set_id` (Python identity partitions).
- `tvscreener.silver`/`tvscreener.gold` are identity-partitioned by `asset_type` + date (when present) + `timeframe_set_id`.
- Overwrite scoping prefers `entity_id` (when present) and otherwise falls back to `PAIR` / `Symbol` / `Name` to avoid deleting unrelated entities inside the same partition.

**Risks / gaps for multi-asset:**

- **Run metadata completeness**: `code_version`, `params_hash`, and `universe_id` are not yet carried through all stages.
- **Scanner family correctness**: `scanner_family` needs to be consistently set (opportunity vs strategy vs other scanners).
- **Health validation drift**: `tvscreener/lib/lakehouse/health.py` exists but does not reflect the canonical column naming used in the lakehouse; the current pipeline primarily gates via in-code checks. A stricter multi-asset validation layer should be redesigned to match real schemas.
- **Dataset taxonomy**: current medallion tables are effectively “TradingView screener snapshots”. Additional dataset types (klines/ticks/orderbooks) should not be forced into the same grain.

## Bottlenecks + suggested improvements (brainstorm summary)

This section is a quick “what will hurt first” review to guide the next design iteration toward
multi-asset + multi-source + multi-screener scaling.

### 1) Upstream throughput + partial runs
- **Risk**: TradingView (and future sources) will rate-limit or partially fail.
- **Mitigation**: keep Bronze append-forensics, but **gate Silver/Gold publish** on coverage metrics,
  and record per-source coverage stats for each run.

### 2) Iceberg write amplification (small files)
- **Risk**: frequent overwrites create many small files + metadata overhead.
- **Mitigation**: periodic compaction + snapshot expiry; batch writes per stage/unit; avoid schema
  union on every write once schemas stabilize.

### 3) Query scalability (Arrow materialization)
- **Risk**: Iceberg → Arrow → DuckDB is memory-bound for large history.
- **Mitigation**: prefer small “product tables” for UX (`signals_latest`, future `signals_batch`) and
  enforce query patterns that prune partitions early (filter on partition columns, limit).

### 4) Wide schemas vs variable timeframe sets
- **Risk**: timeframe-as-columns scales poorly and creates schema churn.
- **Mitigation**: long-form migration path (timeframe as a column) with optional materialized wide
  outputs for matrix UX only.

For the more detailed roadmap + requirements, see OpenSpec:
`docs/openspec/changes/add-multi-asset-multi-source-screener-framework/`.

## Contract: separate data pipelines from analytics pipelines

To enable flexible query backends and analytics patterns, define explicit contracts:

### Data pipelines (canonical)
- Write canonical data/features to Iceberg medallion tables.
- Never depend on a specific query engine.
- Output schema should be stable and replayable at the Iceberg snapshot level.

### Analytics pipelines (products)
- Consume Iceberg identifiers (optionally at a snapshot) and produce:
  - latest-per-entity products (`signals_latest`)
  - batch rollups (`signals_batch`) and strategy-specific outputs
- May use different query backends behind a common contract (DuckDB today; others later).

## Proposed Architecture

### 0) Dataset taxonomy (distinguish data types early)

The current pipeline ingests TradingView screener outputs. Those rows are a distinct dataset type (“screener snapshots”).
When adding other market data, keep dataset types separate by namespace/table design so grains and retention policies do not conflict.

Recommended dataset types:

- `screener_snapshot`: TradingView screener observations (current)
- `klines`: OHLCV bar series (per timeframe)
- `ticks`: trade/quote tick stream
- `orderbook`: L2 snapshots/deltas

Recommended physical layout:

- Separate namespaces (preferred): `tvscreener.screener_*`, `tvscreener.market_klines_*`, `tvscreener.market_ticks_*`, `tvscreener.market_orderbook_*`
- Or separate tables under a single namespace with a required `dataset_type` column (acceptable, but easier to misuse)

### 1) Split pipelines by concern

**Data pipelines** produce canonical, queryable tables:

- Ingestion (raw snapshots) -> Bronze
- Normalization (canonical IDs + columns) -> Silver
- Feature engineering + scoring inputs -> Gold (features)

**Analytics pipelines** consume the lakehouse and emit decision outputs:

- Batch signals (rankings, reports, dashboards)
- Realtime signals ("latest" snapshots, time-travel checks)
- Rendering (matrix/detailed) consumes analytics outputs, not raw ingestion frames

Key contract:

- Data pipelines end at “features are prepared”.
- Analytics pipelines begin only once feature tables are available for a given `asset_type`/timeframe set (universes are applied as query selectors).

### 2) Run identity + metadata (required for multi-asset)

Create a first-class run envelope that every stage attaches (as columns in all tables):

- `run_id`: UUID (idempotency + audit join key)
- `fetched_at_utc`: timestamp of upstream fetch
- `asset_type`: `forex|stocks|crypto|commodity|...`
- `universe_id`: optional selector used to choose the asset list for ingestion (not a partition key)
- `timeframes`: canonical string (sorted, comma-separated, e.g. `15,60,240`)
- `timeframe_set_id`: stable ID derived from `timeframes` (hash), used for grouping and workflow fanout
- `scanner_family`: `opportunity|strategy|...`
- `source`: `tradingview` (future-proof)
- `code_version`: git SHA or version string (so we can reproduce a run against the same logic)
- `params_hash`: stable hash of request parameters (guards accidental drift)

For non-screener datasets, `scanner_family` may be null; prefer a dataset-specific field such as `dataset_type` and/or `pipeline_name`.

Also introduce a `tvscreener.runs` table (or `tvscreener.meta_runs`) keyed by `run_id` recording:

- request params
- start/end times
- produced Iceberg `snapshot_id`s for bronze/silver/gold
- git SHA (optional)

Note on idempotency:

- `run_id` should be globally unique.
- If a workflow engine is used, map the workflow ID directly to `run_id` (or `{env}:{pipeline}:{run_id}`) to guarantee exactly-once orchestration.

### 3) Canonical entity keys (multi-asset safe)

Normalize identity across asset types using canonical columns:

- `entity_id`: stable string ID (e.g. `OANDA:EURCHF`, `NASDAQ:AAPL`, `BINANCE:BTCUSDT`)
- `symbol`: symbol only (e.g. `EURCHF`, `AAPL`, `BTCUSDT`)
- `venue`: exchange/broker code (e.g. `OANDA`, `NASDAQ`, `BINANCE`)
- Keep asset-specific convenience columns (e.g. `PAIR`) but do not depend on them for correctness.

All overwrite scoping and partitioning should use `entity_id` (and optionally `symbol`) instead of `PAIR`.

Also define canonical time semantics across datasets:

- `event_ts`: the market timestamp (bar open/close time, tick time, book snapshot time)
- `as_of_ts`: the ingestion/compute timestamp (when we fetched or computed the row)

Point-in-time (PIT) analytics should be expressed as “select rows where `as_of_ts` is the latest <= query time”.

For all feature/signal tables that power decisions, PIT correctness is non-negotiable. If a table does not have both timestamps, it is not safe for historical audits.

### 4) Table design for variable timeframes

To support different timeframe sets per asset type (and to keep schema stable as timeframes expand), the lakehouse needs a **long form** representation.

#### Bronze: raw observations (long)

Row grain: `run_id, entity_id, timeframe, fetched_at_utc`.

- Contains the direct upstream numeric fields for the timeframe.
- Includes `timeframe` as a column (string or integer minutes).

Partitioning guidance:

- Avoid partitioning by high-cardinality selectors like `run_id`, `universe_id`, or `entity_id` identity.
- Recommended long-term Iceberg partition spec (transforms):
  - `days(event_ts)` for time pruning
  - `identity(timeframe)` where applicable
  - `bucket(N, entity_id)` for scalable pruning without partition explosion

For the current Python-only implementation (identity partitions), start with:

- Partition strategy (initial): `asset_type`, `ingest_date`

Notes by dataset type:

- `screener_snapshot`: `timeframe` is present because TradingView screener results are timeframe-scoped.
- `klines`: `timeframe` is required; `event_ts` is the bar time.
- `ticks`/`orderbook`: no timeframe on raw rows; store `event_ts` and derive time-buckets during feature engineering.

#### Silver: normalized observations (long)

Row grain: same as Bronze.

- Enforces canonical column names and types.
- Adds derived normalized columns that are still “data layer” (not decision layer).

Partition strategy (initial): `asset_type`, `ingest_date`.

#### Gold: features (long)

Row grain: same as Bronze/Silver.

- Adds feature-engineered columns that are safe inputs for analytics (scores per factor, TA features, etc.).
- Does NOT collapse across timeframes by default.

Partition strategy (initial): `asset_type`, `signal_date`.

#### Analytics outputs (separate tables)

Instead of pushing “decision tables” into `tvscreener.gold`, define explicit analytics tables:

- `tvscreener.signals_batch`: aggregated across timeframes per `entity_id` for a run (matrix-ready)
- `tvscreener.signals_realtime`: latest-per-entity view keyed by `entity_id` and updated frequently

This keeps `tvscreener.gold` as “features” and prevents mixing storage concerns with presentation concerns.

Anti-patterns to avoid:

- Partitioning the large fact tables by `run_id` or `universe_id`.
- Table-per-timeframe sprawl unless retention/SLAs differ materially.
- Mixing mutable “latest state” outputs into the same table as append-heavy features.

### 4.5) Universe concept (tradable asset groups)

Universe is a **group of tradable assets** for an intended strategy. It is an input to ingestion (how we select what to pull) and an input to analytics (how we filter what to trade).
It should not change table grain, schema, or partitioning.

Model universes explicitly as membership tables:

- `tvscreener.universes`: `(universe_id, name, asset_type_scope, description, created_at)`
- `tvscreener.universe_members`: `(universe_id, entity_id, weight, valid_from, valid_to, tags)`

For exact reproducibility, snapshot membership per run:

- `tvscreener.run_universe_snapshot`: `(run_id, universe_id, entity_id)`

### 4.6) Schedulable pipeline units (workflow engine friendly)

Schedule ingestion/transform/featurize independently per dataset and routing dimensions:

- Unit key: `(dataset_type, asset_type, timeframe_set)` plus an input selector (`universe_id` or explicit entity list)
- Stages: `ingest` -> `transform` -> `featurize` (each produces a new snapshot)

The workflow engine should be able to run and retry each unit independently.
Analytics pipelines consume only completed/validated feature snapshots.

Practical scheduling model:

- Screener snapshots: scheduled periodic scans per `asset_type` + selector + timeframe set.
- Klines: scheduled or continuous ingestion, then transform/featurize in windows.
- Ticks/orderbooks: continuous ingestion, with separate downsampling/feature windows to avoid unbounded tables.

### 5) Iceberg catalog design

Support two catalog modes:

1. **Local dev** (default): SQLite SQL catalog + file warehouse (current behavior).
2. **Durable workflows**: Postgres SQL catalog + shared warehouse path.

Configuration should be externalized (env/config) rather than hard-coded.
If DBOS is adopted, it is attractive to reuse the same Postgres instance for:

- DBOS workflow state
- Iceberg catalog (SQL catalog)

Concurrency note:

- SQLite catalogs are suitable for single-writer local dev.
- If multiple workers will write concurrently, move to a Postgres-backed SQL catalog.

## Maintenance + backfills (Iceberg hygiene)

If we expect daily/continuous ingestion, we must budget for table maintenance. Without it, query planning will degrade.

Minimum maintenance policy:

- Compaction: rewrite small files into target file sizes (data file rewrite).
- Snapshot retention: expire old snapshots on a safe window.
- Orphan cleanup: remove orphan files after retention windows.
- If using row-level deletes/updates: rewrite delete files periodically.

Backfill strategy:

- Prefer overwrite-by-range (time windows) or overwrite-by-filter for reprocessing rather than frequent MERGE/upserts.
- Record backfill runs as new `run_id`s and keep snapshot metadata for auditability.

## Workflow engine constraints (DBOS-ready)

If using DBOS Transact:

- Keep workflow functions deterministic; all nondeterminism (time, IO, API calls, catalog reads that affect branching) belongs inside `@step` functions.
- Map workflow ID to `run_id` (or `{env}:{pipeline}:{run_id}`) for idempotency.
- Use queues with partition keys to serialize conflicting writes (e.g. per `asset_type` and per table) and to cap global concurrency.
- Store run registry + snapshot artifacts in Postgres; store only pointers/metadata as step outputs.

## Migration Plan (phased)

### Phase 0: Design + acceptance criteria

- Decide whether `tvscreener.gold` remains “signals” or becomes “features” (recommended: gold=features, signals tables separate).
- Agree on canonical identity columns (`entity_id`, `symbol`, `venue`) and run metadata columns.
- Agree on dataset taxonomy boundaries and grains (screener vs klines vs ticks vs orderbook).
- Agree on PIT semantics: required timestamps and how analytics chooses “latest as_of <= T”.

### Phase 1: Add run metadata columns (no breaking changes)

- Add `run_id`, `fetched_at_utc`, `asset_type`, optional `universe_id`, `timeframes`, `timeframe_set_id`, `scanner_family`, `source`, `code_version`, `params_hash` to frames before persisting.
- Update overwrite scoping to use `entity_id` (or the best available identity column) instead of `PAIR`.

### Phase 2: Introduce long-form Bronze/Silver/Gold

- Keep existing wide columns for the default `15,60,240` timeframe set for now.
- Add (or transition to) long-form rows keyed by `timeframe` so new assets/timeframes do not require schema surgery.
- Ensure `event_ts` and `as_of_ts` exist for PIT-safe analysis.

### Phase 3: Split analytics outputs

- Create `signals_batch` and `signals_realtime` tables derived from `tvscreener.gold` (features).
- Ensure matrix/detailed renderers read from analytics outputs.

### Phase 3.5: Add additional dataset-type pipelines

- Add `klines` ingestion/transform/featurize pipeline units and publish feature tables.
- Add `ticks`/`orderbook` ingestion pipelines with clear retention and downsampling strategy, then publish derived time-bucketed features.

### Phase 4: Catalog externalization

- Add configuration for catalog backend (sqlite vs postgres) and warehouse path.
- Add a small “catalog health” command to validate connectivity and list tables.

## Checklist (plan audit)

- Partitions avoid high-cardinality explosion (`run_id`, `universe_id`, raw `entity_id` identity).
- Tables that drive decisions include both `event_ts` and `as_of_ts`.
- `run_id` + `code_version` + `params_hash` are recorded for reproducibility.
- Backfills have a documented overwrite-by-range approach.
- Maintenance tasks are scheduled and owned.
- Analytics consumes feature tables only; presentation does not leak into storage.

## Acceptance Criteria

- Multi-asset reruns do not overwrite unrelated assets/timeframes for the same `signal_date`.
- Different universe selections do not require different table designs; universes are expressed via membership + run snapshots.
- Variable timeframe sets can be ingested without changing the table schema (timeframes are a dimension, not a new set of columns).
- Every persisted row is attributable to a `run_id`, and each run records Iceberg snapshot IDs.
- Analytics tables can produce matrix-ready signals from the canonical feature tables.
- Additional dataset types (klines/ticks/orderbooks) can be ingested and feature-engineered without contaminating the screener snapshot table grain.
