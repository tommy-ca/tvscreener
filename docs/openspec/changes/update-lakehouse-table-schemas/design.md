## Context (current implementation)

## Iceberg catalog / namespace / table semantics (target)

### Canonical references (for audit/validation)
- **PyIceberg SQL catalog identifier rules**: `https://py.iceberg.apache.org/reference/pyiceberg/catalog/sql/`
- **PyIceberg catalog identifier conventions**: `https://py.iceberg.apache.org/reference/pyiceberg/catalog/`
- **Apache Iceberg Spark DDL (CREATE TABLE, PARTITIONED BY, USING iceberg)**: `https://iceberg.apache.org/docs/latest/spark-ddl/`
- **Iceberg TableIdentifier (namespace + name model)**: `https://iceberg.apache.org/javadoc/1.6.1/org/apache/iceberg/catalog/TableIdentifier.html`
- **TradingView `/scan` reference implementation (row shape `s` + `d[]`)**: `https://raw.githubusercontent.com/shner-elmo/TradingView-Screener/master/src/tradingview_screener/query.py`

### Terminology
- **Catalog**: configured via `pyiceberg.load_catalog(...)` (local/remote). In SQL engines this is
  typically the first identifier segment (e.g. `prod_catalog`).
- **Namespace**: Iceberg “schema” grouping for tables (often a SQL schema). In this plan we use
  **stage-oriented namespaces** (e.g. `tvscreener_bronze`, `tvscreener_silver`, `tvscreener_gold`).
- **Table**: dataset name under a namespace (e.g. `screener_snapshot`, `market_klines`).

### Identifier conventions
- **Python / pyiceberg**: use `namespace.table` (catalog is configured out-of-band).
  - Example: `tvscreener_bronze.screener_snapshot`
- **SQL engines (Spark/Trino/etc.)**: often use `catalog.namespace.table`.
  - Example: `local.tvscreener_bronze.screener_snapshot`

### Naming rule (stage-as-namespace, SQL-catalog friendly)
To keep **table names free of stage names**, we encode stage in the **namespace**:

`tvscreener_<stage>.<dataset>`

Examples:
- `tvscreener_bronze.screener_snapshot`
- `tvscreener_silver.screener_snapshot`
- `tvscreener_gold.screener_snapshot`
- `tvscreener_product.signals_latest`

Future datasets:
- `tvscreener_bronze.market_klines`
- `tvscreener_silver.market_klines`
- `tvscreener_silver.market_trades`
- `tvscreener_silver.market_bbo`
- `tvscreener_silver.market_book_l2`
- `tvscreener_silver.market_book_l3`
- `tvscreener_silver.instrument_definitions`
- `tvscreener_silver.deriv_funding`

#### Note on “stage as dotted namespace”
Iceberg/PyIceberg can represent multi-level namespaces (e.g. `tvscreener.bronze.screener_snapshot`),
but our current `LakehouseManager` namespace provisioning is **single-level** (it creates only the
first identifier segment). Using `tvscreener_bronze` avoids nested namespace provisioning complexity
while remaining Iceberg-native.

### Alternative: nested namespace by asset + instrument + stage

As the system expands to asset types whose `/scan` payload schemas are not identical (and to instruments like crypto perps),
a nested namespace layout becomes attractive for isolation.

Logical model:
- `tvscreener.<asset_type>.<instrument_type>.<stage>.<dataset>`

Example:
- `tvscreener.crypto.spot.bronze.screener_snapshot`
- `tvscreener.crypto.perp.gold.screener_snapshot`

Compatibility note:
- If the catalog/backend prefers single-level namespaces, use a flattened physical encoding:
  - `tvscreener_<asset_type>_<instrument_type>_<stage>.<dataset>`

See `docs/openspec/changes/refactor-lakehouse-namespace-layout/` for the proposed contract and migration plan.

### Current table names
The base opportunity pipeline writes to:
- `tvscreener.bronze` (append)
- `tvscreener.silver` (overwrite, scoped)
- `tvscreener.gold` (overwrite, scoped)
- `tvscreener.signals_latest` (overwrite, scoped)

### Current partitions (as implemented)
From `tvscreener/lib/screeners/base.py`:

- `tvscreener.bronze`:
  - `["asset_type", "ingest_date", "timeframe_set_id"]`
- `tvscreener.silver`:
  - `["asset_type", "signal_date", "timeframe_set_id"]` (if `signal_date` present)
  - else `["asset_type", "ingest_date", "timeframe_set_id"]` (if `ingest_date` present)
  - else `["asset_type", "timeframe_set_id"]`
- `tvscreener.gold`:
  - ensures `signal_date` exists
  - `["asset_type", "signal_date", "timeframe_set_id"]`
- `tvscreener.signals_latest`:
  - `["asset_type", "timeframe_set_id"]`

Overwrite scoping is done via Iceberg overwrite filters built from:
- partition columns
- plus an entity key column (prefers `entity_id`, falls back to `PAIR`, `Symbol`, `Name`)
- and ALWAYS includes `IS NULL` checks for partition columns and the selected key column (legacy cleanup)

#### Note on Iceberg overwrite warnings

Some Iceberg engines emit a warning when an overwrite operation internally issues a delete that matches no rows
(e.g. rerunning a partition overwrite for a partition that does not exist yet).

In this repo, this is expected during idempotent reruns and tests, so the lakehouse writer suppresses only the
specific `pyiceberg` warning:

- `UserWarning: Delete operation did not match any records`

All other warnings and exceptions remain visible.

### Current shared “run envelope” columns
Written on every stage row when non-empty:
- `run_id` (uuid string)
- `fetched_at_utc` (datetime)
- `asset_type` (canonicalized string: `forex`, `stock`, `crypto`, `futures`, `bond`, `coin`, …)
- `timeframes` (canonical string, sorted + comma-separated; e.g. `"15,240,60"`)
- `timeframe_set_id` (stable hash of the timeframe set)
- `scanner_family` (currently hard-coded to `"opportunity"` in the base pipeline)
- `source` (currently hard-coded to `"tradingview"` in the base pipeline)

## Current schema definitions (by stage)

### 1) TradingView “screener snapshot” (Bronze)
**Definition**: the raw-ish dataframe returned by `TradingViewScreener.get()` with a selected subset
of fields, plus the run envelope.

#### Upstream TradingView `/scan` response shape (canonical)
TradingView’s scan API returns:
- `totalCount`: integer
- `data`: array of rows
  - each row contains:
    - `s`: a ticker string like `NASDAQ:AAPL`
    - `d`: an array of values aligned positionally with the request’s `columns` list

Example (from the `tradingview-screener` reference implementation):
- `{'totalCount': 17559, 'data': [{'s': 'NASDAQ:NVDA', 'd': [116.14, 312636630]}, ...]}`

This is the **canonical upstream “screener snapshot” record**. Our lakehouse schema should
centralize around this shape (plus the run envelope), and treat the expanded wide dataframe
columns as a Silver/Gold concern.

#### TradingView screener “data types” (what the scan API can represent)
Within `/scan`, “data types” mostly map to **column families** (selected in the request’s `columns`):
- **Identifiers**: `ticker` (our `Symbol`), `name`, `exchange`, `market`, `country`, `currency`, `type`
- **OHLCV-style fields**: `open`, `high`, `low`, `close`, `volume`, `Value.Traded`
- **Fundamentals**: e.g. `market_cap_basic`, P/E variants, balance sheet metrics
- **Technical indicators**: `RSI`, `MACD.*`, moving averages, etc.
- **Timeframe-qualified fields**: many columns support a suffix like `|15`, `|60`, `|240`, `|1W`, `|1M`
  (meaning “same field at a specific timeframe”)
- **Update mode**: `update_mode` indicates whether a row’s values are streaming vs delayed (often dependent
  on exchange entitlements/cookies)

For this repo, a “TradingView screener snapshot” dataset is therefore:
- **Grain**: one row per entity at fetch time (`fetched_at_utc`) for a configured `timeframe_set_id`
- **Payload**: selected `columns[]` and returned `d[]`, plus `s` as the canonical identifier

**Required columns (observed/relied upon by code)**:
- `Symbol` (TradingView-qualified symbol; used for coverage stats and identity fallback)
- `Name` (display name; fallback identity)
- `Price` (price; used by risk calculations via fallback)
- `Subtype` (classification; optional)
- `update_mode` (added to every request in `tvscreener/util.py`)
- run envelope: `run_id`, `fetched_at_utc`, `asset_type`, `timeframes`, `timeframe_set_id`, `scanner_family`, `source`
- Bronze partition helper: `ingest_date` (`YYYY-MM-DD`)

**Requested “base fields” (selected per asset field class)**:
- `NAME`, `PRICE`, `SUBTYPE` (labels: `Name`, `Price`, `Subtype`)
- one of: `AVERAGE_VOLUME_10D_CALC`, `RELATIVE_VOLUME_10D_CALC`, `VOLUME` (if available on the field class)

**Requested “timeframe fields” (per configured timeframe)**:
- recommendations:
  - `Recommend All|{tf}`
  - `Recommend Ma|{tf}`
  - `Recommend Other|{tf}`
- momentum:
  - `Roc|{tf}`
- optional (if enabled):
  - `ATR|{tf}`
  - `RSI|{tf}`

**Forex-specific derived columns (may appear pre-Silver via dedupe logic)**:
- `PAIR` (derived in Silver dedupe for forex; not guaranteed in Bronze)

### 2) Silver normalized “screener snapshot”
**Definition**: Bronze snapshot rows normalized for cross-asset joins and stable column naming.

**Additional required columns (added in Silver)**:
- `venue` (derived from `Symbol` before the `:`)
- `symbol` (derived from `Symbol` after the `:`)
- `entity_id` (preferred stable join key; `{venue}:{symbol}` or `{asset_type}:{raw}` fallback)

**Normalization rules applied** (from `tvscreener/lib/screeners/transformer.py` and `base.py`):
- Technical columns renamed to canonical forms when present:
  - `Recommend All|{tf}` → `TREND_{tf}`
  - `Recommend Ma|{tf}` → `MA_{tf}`
  - `Recommend Other|{tf}` → `OSC_{tf}`
  - `Roc|{tf}` → `ROC_{tf}`
  - `ATR|{tf}` → `ATR_{tf}`
  - `RSI|{tf}` → `RSI_{tf}`
- Stat columns renamed:
  - `Relative Volume (10 day Calc)` → `RVOL`
  - `Average Volume (10 day Calc)` → `AVG_VOLUME`
- Duplicate handling:
  - prefer uniqueness by `entity_id`, else `Symbol`, else `Name`
  - forex overrides with `PAIR`-based dedupe + exchange priority

**Date semantics**:
- Silver may or may not carry a `signal_date` (depends on upstream/derived usage). If present, it becomes a partition axis.

### 3) Gold scored/features schema (opportunity)
**Definition**: Silver rows enriched with scoring + confluence + (optional) risk outputs.

**Gold “score factor” columns** (from `tvscreener/score.py`):
- `TREND_SCORE`, `MA_SCORE`, `OSC_SCORE`, `ROC_SCORE`
- `VOLATILITY_SCORE`
- `ENSEMBLE_SCORE`
- `DIRECTION`

**Gold “confluence/grid” columns**:
- `GRID_ALIGNED`, `GRID_TOTAL`, `GRID_PCT`
- `TOTAL_CONFLUENCE`
- `CONFLUENCE_LEVEL`
- `TF_CONFLUENCE_LONG`, `TF_CONFLUENCE_SHORT`
- per-factor direction labels (when factor score exists): `TREND_DIR`, `MA_DIR`, `OSC_DIR`, `ROC_DIR`
- `FACTOR_BULLISH_COUNT`, `FACTOR_BEARISH_COUNT`
- display columns:
  - `GRADE`
  - `TF_CONFLUENCE` (e.g. `"2/3"`)
  - `FACTOR_CONFLUENCE` (e.g. `"3/4"`)
  - `RATING_SCORE`, `ROC_AVG`

**Optional risk columns** (from `tvscreener/lib/screeners/risk_utils.py`):
- `STOP_LOSS`, `TAKE_PROFIT`, `RR_RATIO`, `POSITION_SIZE`

**Presentation columns (renderer/UX)**:
- `STRENGTH_SIGN`, `DIRECTION_SIGN` (forex opportunity only; added in `forex_opportunity.py`)

**Gold date semantics**:
- If missing, `signal_date` is added at write time (`YYYY-MM-DD`) and used as a partition key.

### 4) `signals_latest`
`signals_latest` is written from the Gold dataframe with partitions:
- `["asset_type", "timeframe_set_id"]`

The schema is effectively **Gold + envelope** with “latest-per-entity” semantics enforced by overwrite scope.

**Naming note**:
- Current implementation table id: `tvscreener.signals_latest`
- Target Iceberg-native product table id: `tvscreener_product.signals_latest` (with the existing table treated as a compatibility alias during migration)

## Issues to address in the schema plan

### Issue: Canonical ROC naming vs ROC scoring
Silver normalization renames `Roc|{tf}` → `ROC_{tf}`, but current ROC scoring looks for `Roc|{tf}`.
Schema updates should pick one canonical form and update scoring accordingly.

### Issue: Multi-dataset support needs explicit taxonomy
Mixing datasets (snapshots, bars, ticks) into a single wide table will create:
- unbounded schema growth
- many null columns
- brittle analytics patterns

## Proposed schema evolution (multi-asset + multi-dataset)

### Guiding principles
- Keep a **shared envelope schema** consistent across all datasets.
- Keep **dataset-specific payload schemas** separate by table (or at least by namespace).
- Prefer **long-form** for variable timeframe sets; materialize wide/matrix outputs as analytics products.

### Dataset taxonomy across asset types (schema packs)
As we expand beyond TradingView screener snapshots, we will ingest datasets whose **canonical schemas already exist**
in market-data ecosystems. Rather than inventing one-off schemas per connector, we treat these upstream conventions
as **schema packs** and map them onto Iceberg tables.

#### Why “schema packs”
- Different asset types (futures / options / perps / CFDs) often share **the same dataset families** (trades, book, bars),
  but differ in **reference/instrument metadata** and in **derivative-only datasets** (funding, open interest, greeks).
- A schema-pack approach keeps “core” dataset schemas stable, while allowing:
  - source-specific extras (via `raw_*` / `flags` / `conditions`)
  - derivative-specific datasets to live in their own tables (so non-derivatives don’t carry nullable columns)

#### Canonical schema pack references (non-exhaustive)
- **Databento DBN**:
  - DBN overview + fixed record structs: `https://github.com/databento/dbn`
  - Example record structs (Rust docs):
    - `RecordHeader`: `https://docs.rs/dbn/latest/dbn/struct.RecordHeader.html`
    - `TradeMsg`: `https://docs.rs/dbn/latest/dbn/struct.TradeMsg.html`
    - `Mbp1Msg`: `https://docs.rs/dbn/latest/dbn/struct.Mbp1Msg.html`
    - `MboMsg`: `https://docs.rs/dbn/latest/dbn/struct.MboMsg.html`
    - `InstrumentDefMsg`: `https://docs.rs/dbn/latest/dbn/struct.InstrumentDefMsg.html`
- **Cryptofeed** (normalized dtype objects):
  - dtype overview: `https://raw.githubusercontent.com/bmoscon/cryptofeed/master/docs/dtypes.md`
  - dtype field definitions: `https://raw.githubusercontent.com/bmoscon/cryptofeed/master/cryptofeed/types.pyx`

#### Important: schema packs apply to Silver (normalized) only
DBN and Cryptofeed are already **normalized record models**. In our medallion architecture:
- **Bronze** focuses on *raw capture* (source payload fidelity + envelope), not on enforcing a normalized market-data schema.
- **Silver** is where we enforce normalized schemas; this is where **schema packs** apply and become the canonical contracts.

#### Target `dataset_type` enum (expanded)
We keep `dataset_type` values **domain-oriented** (not connector-oriented) so multiple sources can populate the same dataset table.

- **Screeners / snapshots**
  - `screener_snapshot` (TradingView `/scan`)
- **Market data (cross-asset)**
  - `market_trades`
  - `market_bbo` (best bid/ask, includes “ticker”/L1 variants)
  - `market_book_l2` (price-level book)
  - `market_book_l3` (order-level book)
  - `market_klines` (OHLCV bars)
- **Reference / symbology**
  - `instrument_definitions` (contract/security reference + point-in-time updates)
  - `symbol_mappings` (source symbology → canonical entity identifiers)
- **Derivatives-only**
  - `deriv_funding` (perpetual swaps)
  - `deriv_open_interest`
  - `deriv_liquidations`
  - `deriv_greeks` (options; future-facing)

#### Mapping examples (schema pack → `dataset_type`)
- **DBN pack**
  - `TradeMsg` → `market_trades`
  - `Mbp1Msg` / `Mbp10Msg` → `market_book_l2`
  - `MboMsg` → `market_book_l3`
  - `InstrumentDefMsg` → `instrument_definitions`
- **Cryptofeed pack**
  - `Trade` → `market_trades`
  - `L1Book` / `Ticker` → `market_bbo`
  - `OrderBook` → `market_book_l2` (and/or `market_book_l3` when depth-by-order is available)
  - `Candle` → `market_klines`
  - `Funding` → `deriv_funding`
  - `OpenInterest` → `deriv_open_interest`
  - `Liquidation` → `deriv_liquidations`

### Shared envelope (all datasets, all medallion stages)
Add/standardize these columns across all datasets:
- `dataset_type` (e.g. `screener_snapshot`, `market_klines`, `market_trades`, `market_book_l2`, `instrument_definitions`)
- `run_id`, `fetched_at_utc`
- `asset_type`, `source`
- `timeframes`, `timeframe_set_id` (for datasets that are timeframe-set scoped)
- `scanner_family` (where applicable)
- `entity_id`, `venue`, `symbol` (where applicable)

### Iceberg table schema registry (DDL-first, central reference)
We treat Iceberg table schemas as a **central contract** that can be expressed as Iceberg SQL DDL.
The Python pipeline may still evolve schemas via `union_by_name`, but the “core columns” below are
the stable contract.

**DDL note**: the snippets below are **Spark-flavored Iceberg DDL** (per the Apache Iceberg Spark DDL docs).
Other engines use similar concepts but may differ in type spellings and `CREATE TABLE` clauses.

#### 1) `tvscreener_bronze.screener_snapshot`
Stores the **canonical upstream shape** (`tv_ticker`, `tv_columns`, `tv_d`) plus the run envelope.

```sql
CREATE TABLE IF NOT EXISTS tvscreener_bronze.screener_snapshot (
  -- Envelope / provenance
  dataset_type STRING,
  source STRING,
  scanner_family STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,
  timeframes STRING,
  timeframe_set_id STRING,

  -- Bronze partition helper (current impl uses YYYY-MM-DD string; target is DATE)
  ingest_date STRING,

  -- Canonical TradingView /scan row shape
  tv_ticker STRING,
  tv_columns ARRAY<STRING>,
  tv_d ARRAY<STRING>
)
USING iceberg
PARTITIONED BY (asset_type, ingest_date, timeframe_set_id);
```

Notes:
- `tv_d` is stored as `ARRAY<STRING>` to avoid “variant” typing issues; Silver owns type casting.
- If/when we need exact raw fidelity, add `tv_row_json STRING` as the authoritative raw payload.

#### 2) `tvscreener_silver.screener_snapshot`
Stores normalized identity + canonicalized columns needed for cross-asset queries.

```sql
CREATE TABLE IF NOT EXISTS tvscreener_silver.screener_snapshot (
  dataset_type STRING,
  source STRING,
  scanner_family STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,
  timeframes STRING,
  timeframe_set_id STRING,

  -- Optional partition helper (present when derived/available)
  signal_date STRING,
  ingest_date STRING,

  -- Canonical identity (join keys)
  entity_id STRING,
  venue STRING,
  symbol STRING,

  -- Canonical “display” fields (normalized from TradingView)
  name STRING,
  price DOUBLE,
  subtype STRING,

  -- Canonical stat fields (optional)
  rvol DOUBLE,
  avg_volume DOUBLE

  -- Technical/timeframe columns are schema-evolved as needed:
  -- TREND_{tf}, MA_{tf}, OSC_{tf}, ROC_{tf}, ATR_{tf}, RSI_{tf}, ...
)
USING iceberg
PARTITIONED BY (asset_type, timeframe_set_id);
```

#### 3) `tvscreener_gold.screener_snapshot`
Stores scoring/confluence/risk features computed from Silver.

```sql
CREATE TABLE IF NOT EXISTS tvscreener_gold.screener_snapshot (
  dataset_type STRING,
  source STRING,
  scanner_family STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,
  timeframes STRING,
  timeframe_set_id STRING,

  -- Partition helper (current impl ensures this exists)
  signal_date STRING,

  -- Identity
  entity_id STRING,
  venue STRING,
  symbol STRING,

  -- Core scoring contract
  ensemble_score DOUBLE,
  direction STRING,
  confluence_level STRING,
  grid_aligned INTEGER,
  grid_total INTEGER,
  grid_pct INTEGER,
  grade STRING,

  -- Optional risk
  stop_loss DOUBLE,
  take_profit DOUBLE,
  rr_ratio DOUBLE,
  position_size DOUBLE
)
USING iceberg
PARTITIONED BY (asset_type, signal_date, timeframe_set_id);
```

#### 4) `tvscreener_product.signals_latest` (analytics product)
“Latest-per-entity” materialization for fast queries and matrix rendering.

```sql
CREATE TABLE IF NOT EXISTS tvscreener_product.signals_latest (
  dataset_type STRING,
  source STRING,
  scanner_family STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,
  timeframes STRING,
  timeframe_set_id STRING,
  signal_date STRING,

  entity_id STRING,
  venue STRING,
  symbol STRING,

  ensemble_score DOUBLE,
  direction STRING,
  confluence_level STRING,
  grid_aligned INTEGER,
  grid_total INTEGER,
  grid_pct INTEGER,
  grade STRING
)
USING iceberg
PARTITIONED BY (asset_type, timeframe_set_id);
```

#### Future: market data dataset types (high-level DDL sketches)

The DDL sketches below define **Silver normalized tables** (schema packs). Bronze raw-capture tables for these
feeds may exist, but are intentionally not standardized here.

**OHLCV bars (`market_klines`)**

```sql
CREATE TABLE IF NOT EXISTS tvscreener_silver.market_klines (
  dataset_type STRING,
  source STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,

  entity_id STRING,
  venue STRING,
  symbol STRING,

  timeframe STRING,
  bar_time_utc TIMESTAMP,
  open DOUBLE,
  high DOUBLE,
  low DOUBLE,
  close DOUBLE,
  volume DOUBLE
)
USING iceberg
PARTITIONED BY (asset_type, timeframe);
```

**Trades (`market_trades`)**

```sql
CREATE TABLE IF NOT EXISTS tvscreener_silver.market_trades (
  dataset_type STRING,
  source STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,

  entity_id STRING,
  venue STRING,
  symbol STRING,

  ts_event_utc TIMESTAMP,
  price DOUBLE,
  size DOUBLE,
  side STRING,

  -- optional, source-specific enrichment (DBN flags/sequence; exchange trade conditions; etc.)
  flags STRING,
  conditions ARRAY<STRING>,
  raw_payload_json STRING
)
USING iceberg
PARTITIONED BY (asset_type);
```

**Best bid/ask (`market_bbo`)**

```sql
CREATE TABLE IF NOT EXISTS tvscreener_silver.market_bbo (
  dataset_type STRING,
  source STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,

  entity_id STRING,
  venue STRING,
  symbol STRING,

  ts_event_utc TIMESTAMP,
  bid_price DOUBLE,
  bid_size DOUBLE,
  ask_price DOUBLE,
  ask_size DOUBLE,

  raw_payload_json STRING
)
USING iceberg
PARTITIONED BY (asset_type);
```

**L2 book snapshots/updates (`market_book_l2`)**

```sql
CREATE TABLE IF NOT EXISTS tvscreener_silver.market_book_l2 (
  dataset_type STRING,
  source STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,

  entity_id STRING,
  venue STRING,
  symbol STRING,

  ts_event_utc TIMESTAMP,
  is_snapshot BOOLEAN,
  depth INTEGER,

  bids ARRAY<STRUCT<price: DOUBLE, size: DOUBLE>>,
  asks ARRAY<STRUCT<price: DOUBLE, size: DOUBLE>>,

  raw_payload_json STRING
)
USING iceberg
PARTITIONED BY (asset_type);
```

**Instrument definitions (`instrument_definitions`)**

```sql
CREATE TABLE IF NOT EXISTS tvscreener_silver.instrument_definitions (
  dataset_type STRING,
  source STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,

  entity_id STRING,
  venue STRING,
  symbol STRING,

  -- minimal cross-asset contract/reference fields
  instrument_id STRING,
  instrument_class STRING,
  underlying_id STRING,
  underlying_symbol STRING,
  currency STRING,
  expiration_utc TIMESTAMP,
  strike DOUBLE,
  contract_multiplier DOUBLE,

  raw_payload_json STRING
)
USING iceberg
PARTITIONED BY (asset_type);
```

**Derivatives: funding (`deriv_funding`)**

```sql
CREATE TABLE IF NOT EXISTS tvscreener_silver.deriv_funding (
  dataset_type STRING,
  source STRING,
  asset_type STRING,
  run_id STRING,
  fetched_at_utc TIMESTAMP,

  entity_id STRING,
  venue STRING,
  symbol STRING,

  ts_event_utc TIMESTAMP,
  mark_price DOUBLE,
  funding_rate DOUBLE,
  next_funding_time_utc TIMESTAMP,

  raw_payload_json STRING
)
USING iceberg
PARTITIONED BY (asset_type);
```

### Migration plan (phased)
- **Phase A (compat)**: add `dataset_type` to current medallion rows (default `screener_snapshot`) and
  update docs/specs to reflect the explicit contract.
- **Phase B (dataset tables)**: route `BaseOpportunityScreener` to stage namespaces:
  - `tvscreener_bronze.screener_snapshot`
  - `tvscreener_silver.screener_snapshot`
  - `tvscreener_gold.screener_snapshot`
  and add new pipelines for other dataset types with their own medallion tables.
- **Phase C (long-form + products)**: introduce long-form storage (optional) and materialized
  “matrix-ready” product tables (`signals_batch`, keep `signals_latest`).

## Audit Findings (design validation)

### Confirmed
- **DBN has fixed record structs that cleanly map to dataset tables**:
  - `TradeMsg` (trades), `Mbp1Msg` (L2 depth-1), `MboMsg` (L3 order-level), and `InstrumentDefMsg` (instrument definitions)
    are explicitly defined in the canonical DBN Rust docs (see links in “Canonical schema pack references”).
- **Cryptofeed exposes normalized dtype objects with stable field sets**:
  - The dtype catalog includes `Trade`, `Ticker`, `OrderBook`, `Candle`, `Funding`, `OpenInterest`, and `Liquidation`
    (see `docs/dtypes.md` + `types.pyx` in the canonical repo).
- **Derivatives require explicit datasets**:
  - Funding/open-interest/liquidations and instrument definitions are separate dataset families in cryptofeed/DBN ecosystems,
    which supports our approach of keeping them out of spot “market_*” tables.

### Mismatches / risks
- **Timestamp semantics vary by source** (e.g., “event time” vs “receive time”):
  - DBN provides both matching-engine event time (`ts_event` via `RecordHeader`) and capture/recv time (`ts_recv` fields).
  - Some realtime feeds may only provide receipt timestamps for certain channels; we must standardize which becomes `ts_event_utc`.
- **Schema-on-read vs schema-on-write tradeoff**:
  - DBN can be stored as decoded columns (best for analytics) or as raw bytes/JSON (best for fidelity). This plan defaults to
    decoded columns + `raw_payload_json` for escape hatches.
- **DDL portability**:
  - `ARRAY<STRUCT<...>>` is supported in Spark-flavored Iceberg DDL but may vary across query backends; product tables should
    prefer scalar columns where possible.

### Follow-ups
- Define the project’s canonical event timestamp contract per dataset (`ts_event_utc` vs `ts_recv_utc`) and enforce it in Silver.
- Add DDL sketches for `deriv_open_interest` and `deriv_liquidations` (and `deriv_greeks` when options are added).
- Decide whether DBN `instrument_id` should be a first-class identity column in Bronze (in addition to `entity_id`).
