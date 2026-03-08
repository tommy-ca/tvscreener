## Design: Binance crypto opportunity scans (spot + perps) via TradingView

### Overview
The Binance integration adds a new `DataSourceAdapter` implementation and a deterministic universe selector.
The shared opportunity scanner continues to run as a two-stage pipeline:

- **Data pipeline**: fetch/standardize/persist medallion tables (Bronze/Silver/Gold) for Binance instruments.
- **Analytics pipeline**: query Iceberg-backed Gold rows to produce ranked + matrix-ready results and artifacts.

### Upstream contract: TradingView `/scan` (crypto)

This workflow uses TradingView's crypto screener endpoint (`https://scanner.tradingview.com/crypto/scan`).
Minimum columns needed for selection + filtering:
- `Exchange` (filter to `BINANCE`)
- `Type` (`spot` vs `swap`)
- `Price`, `High`, `Low` (for 24h volatility proxy)
- `Volume 24h in USD` (for top-N ranking and min-volume filter)

Observed examples:
- spot: `BINANCE:BTCUSDT` with `Type=spot`, `Subtype=crypto`
- perp: `BINANCE:BTCUSDT.P` with `Type=swap`, `Subtype=crypto`

### Instrument identity

TradingView requires distinguishing spot vs perps.

Canonical identity fields (applies to all persisted rows):
- `venue`: `binance` (derived from `Exchange`)
- `instrument_type`: `spot | perp` (derived from `Type` as `spot|swap`)
- `symbol`: e.g. `BTCUSDT` (derived from TradingView `Symbol` after `BINANCE:`)
- `entity_id`: `binance:spot:BTCUSDT` or `binance:perp:BTCUSDT`

This keeps spot/perps from polluting each other’s datasets and supports downstream joins.

### Universe selection (deterministic)

Universe selector produces a list of `entity_id` values given constraints:
- market types: spot + perps
- rank: top 100 by 24h quote volume (USD)
- filters:
  - quote volume USD >= 10,000,000
  - 24h volatility >= 3%

Definitions:
- `quote_volume_usd`: TradingView `Volume 24h in USD`.
- `volatility_24h_pct`: prefer TradingView native `Volatility` (`CryptoField.VOLATILITY` / `Volatility.D`).
  - fallback: `(High - Low) / Price * 100`

### Artifacts and reproducibility

The run MUST persist, at minimum:
- `run_spec.json`
- `run_result.json`
- `*_results.parquet` (analytics)
- `matrix.txt` (when matrix requested)

Additionally for universe reproducibility, persist an **universe snapshot artifact** under the run dir:
- `universe.json` (list of selected instruments + rank metrics at selection time)

### Parity with forex opportunity scanner

The same opportunity scanner family should be used across asset types.
Any Binance-specific differences are constrained to:
- universe selector (TradingView-filtered)
- identity normalization (`instrument_type` + venue)

The analytics and rendering contracts remain stable (matrix view columns derived from Gold).

### Lakehouse table isolation (asset-type schema differences)

TradingView field availability differs across asset types.
To keep Iceberg schemas stable while preserving multi-asset capability:

- Persist only a **common, cross-asset** screener snapshot schema into shared medallion tables.
- Treat asset-specific payloads as:
  - separate dataset tables (`dataset_type`), and/or
  - asset-specific Silver/Gold tables, and/or
  - a `payload_json` column in Bronze for optional extra fields.

This aligns with `docs/openspec/changes/update-lakehouse-table-schemas/` which emphasizes dataset-aware tables and
explicit derivative datasets.
