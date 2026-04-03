# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Strategy layering and feature datasets

### Strategy layering model

Each strategy family is an analytics layer over a **shared base universe** + derived features.

- **Base universe**: start from a tradeable-first universe, then apply strategy-specific filtering/ranking in analytics.

Recommended mapping:
- TS strategies (TSMOM/TSMR): `binance_{spot,perp}_tradeable_base`
- CS strategies (CSMOM/CSMR): `binance_{spot,perp}_tradeable_mcap_cs`

Convenience aliases:
- `binance_{spot,perp}_base` -> `binance_{spot,perp}_tradeable_base`
- `binance_{spot,perp}_largecap` -> `binance_{spot,perp}_tradeable_mcap_cs`

Default stance:
- Use `binance_{spot,perp}_tradeable_base` as the common base universe across strategies.
- For cross-sectional strategies, optionally apply an analytics-stage market-cap anchor (or swap the input universe to `*_tradeable_mcap_cs`).

Avoid using `binance_{spot,perp}_top100` as a strategy base; it is a volume snapshot universe.
Prefer `binance_{spot,perp}_tradeable_base` (shared strategy base) and apply strategy-specific rankers/filters in analytics.
- **Eligibility gates**: applied in universe selection (liquidity, exclusions).
- **Ranking/filtering**: applied in analytics (DuckDB) and persisted as results parquet.

### Audit and readiness

Use the audit+report pipeline to validate a base universe is strategy-ready:
- quote purity (USDT/USDC)
- base duplication rate
- spot vs perp parity by family
- risky exclusions (short-history non-mcap bases)
- volume distribution (percentiles + bins)

Recommended checks for the default strategy bases:
- `tradeable_base`: verify `excluded_risky` is non-zero and duplicates are zero.
- `tradeable_mcap_cs`: expect smaller counts due to market-cap mapping and liquidity gates; verify spot/perp base overlap is high.

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
