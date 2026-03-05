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

## Impact
- Affected specs (new):
  - `multi-asset-pipeline`
  - `data-sources`
  - `screener-framework`
  - `analytics-pipelines`
- Affected docs (update):
  - `docs/plans/2026-03-02-duckdb-edge-architecture.md` (reflect Iceberg-first reality)
  - `docs/brainstorms/2026-03-03-tradingview-scanner-pipeline-scale.md` (bottlenecks + roadmap)

