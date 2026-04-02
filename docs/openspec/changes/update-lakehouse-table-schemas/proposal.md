# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Change: Update lakehouse table schemas (multi-asset + multi-dataset)

## Why
The lakehouse is already **multi-asset** at the pipeline level (`asset_type` partitions + identity keys),
but the **table schema design** is still implicitly centered on a single dataset type: TradingView
screener snapshots.

To scale to multiple asset types *and* multiple dataset types (screener snapshots, OHLCV bars,
trades, BBO, L2/L3 order books, instrument definitions, and derivative-only feeds like funding/open interest),
we need explicit schema contracts that:
- keep **shared envelope/provenance** stable
- define **dataset-specific payload shapes** without ballooning wide nullable schemas
- keep Bronze/Silver/Gold semantics consistent across datasets

## What Changes
- Define the **current implemented schema** for:
  - TradingView screener snapshots (Bronze)
  - Silver normalized screener snapshot rows
  - Gold scored/features rows (including `signals_latest`)
- Define a **schema evolution plan** for multi-dataset support:
  - Introduce `dataset_type` as a first-class axis (and partition where appropriate)
  - Specify Iceberg-native table naming conventions for per-dataset medallion tables (`namespace.table`)
  - Specify which columns are shared vs dataset-specific
  - Define how “wide-form” multi-timeframe features evolve toward long-form representations
  - Adopt **schema packs** (e.g. DBN, Cryptofeed-style schemas) as canonical sources for market-data dataset shapes

## Impact
- Affected code (future implementation; this change is planning/spec only):
  - `tvscreener/lib/screeners/base.py` (table selection + envelope + partitions)
  - `tvscreener/lib/screeners/transformer.py` (Silver normalization contract)
  - `tvscreener/score.py` + `tvscreener/lib/screeners/risk_utils.py` (Gold schema contract)
  - `tvscreener/lib/lakehouse/manager.py` (naming/namespace conventions; optional)
- Affected docs/specs:
  - This OpenSpec change package
  - `docs/architecture/LAKEHOUSE.md` (follow-up once implemented)

