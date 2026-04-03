# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
date: 2026-03-03
topic: tradingview-scanner-pipeline-scale
---

# Scaling the TradingView Scanner Pipeline (Multi-Asset, Many Symbols)

## What We're Building

Make `tvscreener`'s current TradingView scanner pipeline robust at large scale (multiple asset types, large universes per asset type, frequent scans) while keeping the existing medallion model (Bronze -> Silver -> Gold) and local Iceberg + edge DuckDB analytics.

This brainstorm focuses on correctness + operability first (no silent partial runs), then scalability (partitioning, query strategy, and run metadata).

## Current Implementation (Reality Check)

- Upstream data comes from TradingView scanner endpoints (`scanner.tradingview.com/<subtype>/scan`) via `Screener.get()`.
- Ingestion batches tickers and concatenates results; batch failures are logged but do not fail the run.
- Iceberg persistence is tied to `tvscreener.{bronze,silver,gold}` and overwrite scoping is currently forex-centric (`PAIR`).
- Edge analytics uses DuckDB but Iceberg reads are materialized as Arrow (no DuckDB extensions).
- CLI "multi-asset" flags exist, but asset routing/universe selection is still effectively forex-first.

## Success Criteria (Operational)

- Every run is traceable: `run_id`, `fetched_at_utc`, `asset_type`, `timeframes` are carried through all stages.
- No silent partial ingestion: coverage is measured and enforced before publishing Silver/Gold.
- Multi-asset correctness: keys and overwrite scope work for non-forex assets.
- Scalable querying: common audits and dashboards do not require loading entire Iceberg tables into memory.

## Bottlenecks (observed + expected)

### 1) TradingView API throughput + partial runs
- **Bottleneck**: upstream rate limits and transient failures cause partial symbol coverage.
- **Current mitigation**: retry/backoff in the TradingView client + ingest coverage gating before publishing Silver/Gold.
- **Next**: per-source concurrency controls and durable “run unit” retry semantics (so we can re-run only failed subsets).

### 2) Iceberg write amplification (small files)
- **Bottleneck**: frequent overwrites can produce many small files and metadata churn.
- **Next**:
  - explicit compaction workflows (maintenance hook + scheduled compaction)
  - avoid schema union on every write when schema is stable
  - batch writes per stage (single Arrow table per scan unit)

### 3) EdgeQueryClient scaling (Arrow materialization)
- **Bottleneck**: querying large historical tables requires scanning to Arrow first.
- **Next**:
  - “product tables” (`signals_latest`, future `signals_batch`) for common queries
  - default audit queries always filter on partition columns and limit early
  - for very large history: time-windowed scans and explicit snapshot selection

### 4) Timeframes as columns (wide schema)
- **Bottleneck**: adding timeframes expands schema and complicates variable timeframe sets.
- **Next**: phase toward long-form medallion (timeframe as a column), with materialized wide views for UX only.

## Key Ideas

### 1) Canonical identity columns (non-negotiable)

Add and standardize these columns across Bronze/Silver/Gold (even if some are null early):

- `asset_type`: `forex|stocks|crypto|commodity|...`
- `venue`: exchange/broker where available (derive from `Symbol` like `OANDA:EURUSD` -> `OANDA`)
- `symbol`: symbol only (`EURUSD`, `AAPL`, `BTCUSDT`)
- `entity_id`: stable join key (`{venue}:{symbol}` when venue exists, else `{asset_type}:{symbol}`)

This replaces the current implicit reliance on `PAIR` for correctness.

### 2) Run envelope + durability

Attach a run envelope as columns in every stage:

- `run_id` (uuid)
- `fetched_at_utc` (timestamp)
- `ingest_date` (YYYY-MM-DD, derived from fetched_at)
- `timeframes` (sorted, comma-separated)
- `timeframe_set_id` (hash of `timeframes`)
- `scanner_family` (`opportunity|strategy|custom|...`)
- `source` (`tradingview`)

Also create/maintain a `tvscreener.runs` meta table keyed by `run_id` capturing request params + stage snapshot IDs.

This aligns with `docs/plans/2026-03-03-multi-asset-iceberg-catalog-and-table-design-plan.md`.

### 3) Coverage-aware ingestion (stop shipping partial data)

Today: failed batches are logged and the run proceeds.

Proposed:

- Track `requested_tickers_count`, `unique_symbols_returned`, `failed_batch_count`, `error_rate`.
- Define a policy per stage:
  - Bronze can append partial rows (for forensic replay) but must record the coverage metrics.
  - Silver/Gold must enforce a minimum coverage threshold for publishing (circuit breaker).

This makes the pipeline predictable under 429s/timeouts.

### 4) Overwrite scoping must be asset-agnostic

Current overwrite scoping uses `PAIR` and date partitions.

Proposed overwrite scoping should use:

- partition columns (e.g. `asset_type`, `signal_date`)
- plus `entity_id`

This prevents scanning a subset of symbols from deleting unrelated symbols inside the same partition.

### 5) Query scalability (stop full-table Arrow materialization)

EdgeQueryClient currently loads Iceberg tables into Arrow before query execution.

To scale:

- Prefer query patterns that push down filters/limits before materialization.
- Keep "audit" tables small and curated (e.g. a `signals_latest` table) so common queries avoid scanning historical Gold.

If we keep extensions disabled, the pragmatic path is to materialize only the partitions needed for a query (partition pruning + snapshot selection), not the whole table.

## Approaches

### Approach A: Stabilize the existing wide tables (Recommended first)

Keep the current wide-row shape (many `TREND_60`, `MA_240`, etc columns) but add:

- canonical identity columns (`entity_id` etc)
- run envelope columns (`run_id`, `timeframe_set_id`, `fetched_at_utc`)
- coverage-aware health gating
- asset-agnostic overwrite scoping

Pros: fastest path to multi-asset correctness; minimal refactor.
Cons: variable timeframe sets still create schema churn and wide rows scale poorly.

### Approach B: Migrate Bronze/Silver/Gold to long-form (Recommended second)

Represent timeframe as a column (`timeframe`) and store factors as canonical columns per row.

Pros: truly supports variable timeframe sets and avoids schema explosion.
Cons: larger refactor and requires reworking scoring logic to aggregate by `entity_id`.

### Approach C: Split ingestion and analytics into separate durable jobs

Turn the CLI scan into a producer that only writes Bronze + run metadata; analytics jobs build Silver/Gold asynchronously.

Pros: better retry semantics and isolation of rate limits.
Cons: more moving parts (scheduler/queue) and more complexity.

## Open Questions

- Target scale: per asset type, how many symbols and how often do you scan (hourly, 15m, 1m)?
- Do you need multi-process concurrency, or is single-writer acceptable for now?
- Do you require time-travel auditing for decisions (PIT correctness), or is "latest snapshot" the main consumer?

## Next Steps

- Decide Approach A vs A->B migration path.
- Implement multi-asset routing fixes (CLI asset_type normalization + universe resolution).
- Add `run_id` + coverage gating and switch overwrite key from `PAIR` to `entity_id`.

## Roadmap pointer (OpenSpec)

For the multi-asset + multi-source + multi-screener expansion plan, see:
`docs/openspec/changes/add-multi-asset-multi-source-screener-framework/`.
