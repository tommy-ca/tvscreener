# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Change: Multi-asset, multi-source, multi-screener pipeline framework

## Why
The current pipeline is effective for **forex + TradingView** and has recently been stabilized as
Iceberg-first (Bronze/Silver/Gold) with DuckDB/Narwhals used for edge analytics. However, scaling to:

- multiple **asset types** (forex, stocks, crypto, futures, ...)
- multiple **data sources** (TradingView + broker/exchange APIs, market data vendors, internal feeds)
- multiple **screener families** (opportunity rankings, strategy signals, filters, and custom scanners)
- multi **timeframe sets** (variable timeframe combinations per scan and per asset type)

requires clearer contracts between ingestion, transformation, feature computation, and analytics
outputs, plus stronger provenance and reproducibility guarantees.

## What Changes
- Define a first-class **pipeline framework** for multi-asset screening:
  - explicit dataset taxonomy (screener snapshot vs klines vs ticks vs orderbook)
  - a consistent **run envelope** and provenance contract across tables
  - a multi-timeframe model that treats `timeframe_set_id` and/or `timeframe` as first-class keys
  - a strict separation between:
    - **data pipelines** (produce canonical Iceberg tables)
    - **analytics pipelines** (consume those tables to produce decision outputs)
  - standard interfaces for **data sources** and **screeners**
  - explicit analytics output tables (e.g. `signals_latest`, `signals_batch`) as products of analytics
    pipelines, not side effects of ingestion
- Add requirements/specs and a design document that identify bottlenecks and the concrete path to:
  - multi-asset correctness (identity keys, overwrite scoping, universe membership)
  - multi-source ingestion (source adapters, failover, coverage/health gating)
  - multi-screener composition (rankers + filters + strategy-specific logic)
  - flexible analytics backends (DuckDB today; other query backends later) with the same analytics contract

## Delivery Priority (FR before NFR)

### Functional requirements (ship first)
1. Multi-asset correctness in persisted contracts:
   - canonical identity (`asset_type`, `entity_id`) and non-destructive overwrite scope
2. Multi-timeframe correctness:
   - stable `timeframe_set_id` + optional per-row `timeframe` for long-form evolution
3. Source-agnostic ingestion:
   - `DataSource` adapter contract and source provenance on Bronze
4. Scanner/screener orchestration at scale:
   - deterministic fan-out over `asset_type x universe_shard x timeframe_set x scanner_family`
5. Analytics product consistency:
   - stable outputs (`signals_latest`, `signals_batch`) across scanner families

### Non-functional requirements (defer until FR baseline is stable)
- Performance optimization (compaction cadence, Arrow materialization tuning)
- Workflow/platform hardening (additional orchestration engines, advanced retry policy tuning)
- Extended observability and SLO dashboards beyond minimum correctness gates

This change explicitly prioritizes FR completion over NFR optimization to reach a usable,
scalable multi-asset, multi-timeframe screener/scanner baseline faster.

## Current Status Review

Functional baseline status for this change package is now complete:
- FR-1 to FR-5 implementation baseline delivered (identity/overwrite safety, timeframe-set contracts,
  source adapters, screener registry/composition, analytics product tables)
- verification smoke completed for multi-asset and multi-timeframe contracts
- deterministic fan-out contract validated with stable `params_hash` expansion behavior

Next execution focus moves to deferred NFRs, but only with FR regression gates kept green.

Operational transition target:
- rerun scanners via Prefect workflows as the standard orchestration path
- scanner CLI default runner switched to Prefect after readiness audits passed

## Expansion readiness audit target

Next planning objective is to audit readiness for expanding beyond current forex-led workflows to:
- commodities
- cryptocurrencies
- equities

The audit will evaluate whether existing contracts are sufficient without schema/orchestration forks,
and identify explicit gaps before production-scale rollout.

Current readiness classification:
- equities: `ready-with-gaps`
- cryptocurrencies: `ready-with-gaps`
- commodities: `blocked`

## Rescheduled preparation focus

Execution is rescheduled to prioritize multi-asset expansion readiness before additional NFR work.

Preparation order:
1. close strategy parity gap for non-forex assets
2. introduce asset-specific universe selector semantics
3. add non-forex ticker normalization/validation guardrails
4. rerun multi-asset/multi-timeframe Prefect smoke for readiness reclassification
5. resume deferred NFR track after expansion prep gates are green

## Impact
- Affected specs (new):
  - `multi-asset-pipeline`
  - `data-sources`
  - `screener-framework`
  - `analytics-pipelines`
- Affected docs (update):
  - `docs/plans/2026-03-02-duckdb-edge-architecture.md` (reflect Iceberg-first reality)
  - `docs/brainstorms/2026-03-03-tradingview-scanner-pipeline-scale.md` (bottlenecks + roadmap)
