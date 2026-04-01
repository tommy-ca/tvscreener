# Medallion Lakehouse Architecture

This project follows a **Medallion Architecture** to manage the data lifecycle from raw TradingView API responses to high-quality, actionable trading signals.

## Data Flow Overview

```mermaid
graph LR
    TV[TradingView API] --> Bronze[Bronze Layer<br/>Raw Ingestion]
    Bronze --> Silver[Silver Layer<br/>Standardization]
    Silver --> Gold[Gold Layer<br/>Scoring & Risk]
    Gold --> App[Downstream Apps<br/>CLI / MCP / Notebooks]

    subgraph "Local Storage (Iceberg + DuckDB)"
        Bronze
        Silver
        Gold
    end
```

## Layers

### 1. Bronze (Raw Ingestion)
- **Source**: Directly from `tvscreener` library calls to TradingView.
- **Content**: Raw, unformatted JSON/Dictionary data converted to DataFrames.
- **Storage**: Appended to Iceberg tables with identity partitions including `asset_type`, `ingest_date`, and `timeframe_set_id`.
- **Purpose**: Data lineage and "replay" capability. If logic changes, we can re-process from Bronze without hitting the API.

### 2. Silver (Standardization)
- **Source**: Bronze layer or fresh ingestion.
- **Content**: Canonical column names (e.g., `CLOSE`, `VOLUME`), standardized asset identifiers (e.g., `EURUSD` instead of `FX:EURUSD`), and basic technical indicators.
- **Storage**: Overwritten to Iceberg tables with identity partitions including `asset_type` and `timeframe_set_id` (and a date column when present).
- **Purpose**: Clean, high-performance dataset for analysis. Enables cross-asset queries.

### 3. Gold (Scoring & Serving)
- **Source**: Silver layer.
- **Content**: Calculated confluence scores, trend strength, volatility metrics, and risk management parameters (Stop Loss, Take Profit, Position Sizing).
- **Storage**: Finalized results ready for consumption.
- **Purpose**: Actionable signals. This is what the user sees in the CLI and MCP tools.

## Data pipelines vs analytics pipelines

This repo treats **multi-timeframe screening** as two distinct pipeline concerns:

- **Data pipelines (canonical)**:
  - Produce **Iceberg medallion tables** (current: `tvscreener.bronze`, `tvscreener.silver`, `tvscreener.gold`)
  - Planned (dataset-aware, Iceberg-native): stage namespaces + dataset tables:
    - `tvscreener_bronze.screener_snapshot`
    - `tvscreener_silver.screener_snapshot`
    - `tvscreener_gold.screener_snapshot`
  - Carry a run envelope (`run_id`, `fetched_at_utc`, `timeframes`, `timeframe_set_id`, `asset_type`, `source`, `scanner_family`)
  - Focus on correctness, replayability, and stable schemas

- **Analytics pipelines (products)**:
  - Consume Iceberg tables (optionally at a specific snapshot) and emit analytics products such as:
    - current: `tvscreener.signals_latest` (latest-per-entity, matrix-ready)
    - planned: `tvscreener_product.signals_latest` (product namespace)
    - future `signals_batch` (batch rollups per run/date)
  - Are allowed to choose different query backends, as long as they honor the same analytics contract
    (DuckDB today; other backends later)

This separation lets us evolve analytics patterns and query engines without breaking canonical data storage.

## Execution layer (local runner vs workflow engines)

Pipeline *definition* is kept engine-agnostic and can be represented as a JSON-serializable `PipelineRunSpec`.
Execution is delegated to a runner:

- **Local runner**: executes in-process (current default CLI behavior)
- **Export runner**: emits `PipelineRunSpec` JSON for external orchestration systems to submit as run config/parameters
- **Prefect runner**: executes the spec via a Prefect flow (default CLI runner; requires a Prefect API endpoint)

Operational defaults:
- Default: run with Prefect (`--runner prefect`) and a configured `PREFECT_API_URL`
- Explicit fallback: `--runner local` for debugging/offline execution

Workflow engines (Dagster/Prefect/Temporal/Airflow/Argo/etc.) are integrated via lightweight adapters/wrappers that live
outside the core `tvscreener` library package so the core remains dependency-free.

## Operational reruns (forex majors/minors)

The repo supports deterministic reruns for **forex majors and minors** using batch fan-out executed through the extension module (`tvscreener_ext`).

- Batch specifications and pipeline entrypoints are managed inside `extensions/src/tvscreener_ext/`.
- Artifacts are keyed by `params_hash` and written under `artifacts/runs/<params_hash>/` so replays are stable and
  machine-discoverable.

Legacy compatibility: `artifacts/prefect/<params_hash>/` remains supported during migration.
- Expected behavior:
  - **Data** runs update canonical Iceberg tables (Bronze/Silver/Gold + product tables such as `signals_latest`).
  - **Analytics** runs are expected to be **read-only** w.r.t. Iceberg and only emit artifacts (e.g. results parquet).

## Multi-timeframe model

- **timeframes**: the configured timeframe list for a scan (e.g. `15,60,240`), stored as a canonical string.
- **timeframe_set_id**: a stable ID derived from `timeframes` and used to keep different timeframe sets from colliding.

Today the lakehouse stores **wide-form** rows (timeframe-as-columns) for matrix UX. The long-term direction
is to support **long-form** medallion tables with a `timeframe` column, and then materialize wide “matrix”
outputs as analytics products.

## Technology Stack

- **Table Format**: [Apache Iceberg](https://iceberg.apache.org/) (via `pyiceberg`) for transactional consistency and time-travel.
- **Storage Backend**: Local Parquet files organized by the Iceberg spec.
- **Query Engine**: [DuckDB](https://duckdb.org/) for lightning-fast OLAP queries on the Edge.
- **Lazy Processing**: [Narwhals](https://github.com/narwhals-dev/narwhals) for agnostic, lazy-evaluated transformations that work across Pandas, Polars, and DuckDB.

## Configuration (local vs remote catalog)

The lakehouse catalog/warehouse is configured via layered settings (YAML + ENV).

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

ENV example:

```bash
export TVSCREENER_LAKEHOUSE_CATALOG_MODE=remote
export TVSCREENER_LAKEHOUSE_CATALOG_REMOTE_URI="postgresql+psycopg://user:pass@host:5432/iceberg"
export TVSCREENER_LAKEHOUSE_CATALOG_REMOTE_WAREHOUSE="s3://bucket/warehouse"
```

## Time Travel & Replay

Since we use Iceberg, we can query historical snapshots of our data:

```python
from tvscreener.lib.query import EdgeQueryClient

with EdgeQueryClient() as client:
    # Query a specific historical snapshot
    df = client.query_sql("tvscreener.gold", "SELECT * FROM df", snapshot_id=123456789)
    # Planned dataset-aware naming:
    # df = client.query_sql("tvscreener_gold.screener_snapshot", "SELECT * FROM df", snapshot_id=123456789)
```

## Maintenance

Lakehouse maintenance can be performed via the CLI:

```bash
uv run tvscreener-scan maintenance --expire-snapshots --days 7 --table tvscreener.gold --config tvscreener.yaml
```
