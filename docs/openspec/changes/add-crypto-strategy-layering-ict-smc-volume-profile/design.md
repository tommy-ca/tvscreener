## Design: Strategy layering and feature datasets

### Strategy layering model

Each strategy family is an analytics layer over a **base universe** + derived features.

- **Base universe**: one of the existing Binance universes (`*_mcap_top100`, `*_cs_momentum`, `*_top100`).

Recommended mapping:
- TS strategies (TSMOM/TSMR): `binance_{spot,perp}_tradeable_base`
- CS strategies (CSMOM/CSMR): `binance_{spot,perp}_tradeable_mcap_cs`

Avoid using `binance_spot_top100` as a strategy base because it includes non-USD quote assets (TRY/JPY/BRL/EUR),
which breaks comparability to perps.
- **Eligibility gates**: applied in universe selection (liquidity, exclusions).
- **Ranking/filtering**: applied in analytics (DuckDB) and persisted as results parquet.

### Strategy definitions (high-level)

TSMOM (time-series momentum):
- per-instrument momentum score from multi-horizon returns / ROC
- trend confirmation (MA slope / regime filter)

TSMR (time-series mean reversion):
- per-instrument deviation from mean (z-score vs SMA/VWAP)
- reversal confirmation (RSI bands + market-structure sweep)

CSMOM (cross-sectional momentum):
- rank the universe by momentum score (same horizons)
- long top decile / short bottom decile (direction configurable)

CSMR (cross-sectional mean reversion):
- rank by negative return / stretched RSI / distance from value areas
- select strongest reversion candidates with structure confirmation

### Required datasets

1) `screener_snapshot` (existing)
- best for coarse selection and fast reruns

2) `market_bars` (new)
- OHLCV bars for each ticker + timeframe
- minimum: 15m/1h/4h bars (matching the default timeframes)

3) Derived feature datasets (new)
- `smc_features` (ICT/SMC)
  - swing highs/lows
  - BOS/CHOCH
  - liquidity sweep flags
  - order block / FVG heuristics (optional, later)
- `volume_profile` (approx from bars)
  - session VWAP
  - volume-at-price histogram approximation
  - POC/VAH/VAL

### Where data lives (schema isolation)

Use the scalable lakehouse layout to prevent schema collisions:

- `tvscreener_crypto_<instrument_type>_bronze.screener_snapshot`
- `tvscreener_crypto_<instrument_type>_silver.market_bars`
- `tvscreener_crypto_<instrument_type>_gold.smc_features`
- `tvscreener_crypto_<instrument_type>_gold.volume_profile`

### Artifacts

Strategy runs should persist:
- `run_spec.json`, `run_result.json`
- results parquet (ranked candidates)
- `matrix.txt` when requested

Universe runs already persist `universe.json` for reproducibility.
