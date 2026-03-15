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
  - exclude stable/wrapped bases
  - de-dupe to one ticker per base (prefer primary quote)

Definitions:
- `quote_volume_usd`: TradingView `Volume 24h in USD`.
- `volatility_24h_pct`: prefer TradingView native `Volatility` (`CryptoField.VOLATILITY` / `Volatility.D`).
  - fallback (per-row): `(High - Low) / Price * 100` when native is missing

Volatility is persisted for later analytics filtering/ranking; it is not used as a base-universe selection gate.

Underfill analysis:
- top-by-volume universes persist a `diagnostics` object in `universe.json` with candidate counts per filter step

Alternative selection mode (planned):
- select coins by market cap top 100 (TradingView `CoinScreener` `Market Cap Calc`)
- map to Binance markets for `quote_assets` (default `USDT`, fallback `USDC`) (spot or perp)
- emit the raw universe (no filters) and persist `universe.json` with `quote_volume_usd` and `volatility_24h_pct`
- filter/sort in analytics using DuckDB (EdgeQueryClient)

### Universe taxonomy (base vs derived)

As we add multiple Binance universes, it helps to distinguish:

- **Base universes** (broad membership; minimal selection-time filters)
  - e.g. market-cap-seeded universes that persist `requested_tickers` and `missing_tickers`
- **Derived universes** (eligibility gates for a specific strategy)
  - e.g. liquidity-gated CS momentum candidates
- **Pre-filtered universes** (selection-time thresholds)
  - e.g. top-N by volume with min volume + min volatility

Guideline: keep base universes raw and do ranking/thresholding in DuckDB analytics unless there is a clear upstream limit.

For `binance_{spot,perp}_top100`, restrict quotes to `USDT`/`USDC` so the universe is USD-quote-aligned.

Note: `min_quote_volume_usd` is treated as a soft hint for the top-by-volume snapshot universes; if it would underfill the requested `top_n`, selection falls back to ranking without the floor so `*_top100` stays exactly 100.

### Audit tooling

Use the built-in audit command to generate a structured report of universe health:

```bash
uv run tvscreener-scan audit binance-universes --out-dir artifacts/audits/binance-universes
```

The audit report includes `quote_asset_dist` so we can spot non-USD quote markets (common in spot top-N lists).

Generate richer distributions and overlap comparisons via DuckDB:

```bash
uv run tvscreener-scan report binance-universes \
  --in-dir artifacts/audits/binance-universes \
  --out-dir artifacts/reports/binance-universes
```

Use `## binance_spot_top100 Quote Overview` in the report to see
how much of spot top100 is non-USD-quoted (TRY/JPY/EUR/BRL/etc).

Use `## Spot vs Perp Parity` in the report to compare spot/perp universes by family.

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

Recommended operator workflow:
- Use `majors`/`minors` universes for crypto opportunity scans (forex-like), and validate via `review binance-universes`.

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

### Data-pipeline validation

If `--pipeline analytics` returns empty unexpectedly, validate that the data pipeline published Iceberg rows:

```bash
uv run tvscreener-scan query tvscreener.signals_latest \
  --sql "SELECT asset_type, count(*) AS n FROM df WHERE asset_type='crypto' GROUP BY 1"
```

Note: some TradingView sources return float-like volume fields; the data pipeline normalizes common count-like columns
to integer types before persisting to keep shared Iceberg schemas stable.

When using shared (legacy) Iceberg tables, avoid concurrent local data scans that write to the same tables.
