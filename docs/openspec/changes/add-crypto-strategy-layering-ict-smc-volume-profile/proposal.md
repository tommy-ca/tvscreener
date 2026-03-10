## Proposal: Strategy layering on Binance universes (TS mom/MR, CS mom/MR) with ICT/SMC + volume profile features

### Goal
Define how to build four strategy families on top of the existing Binance universes:

- **TSMOM** (time-series momentum)
- **TSMR** (time-series mean reversion)
- **CSMOM** (cross-sectional momentum)
- **CSMR** (cross-sectional mean reversion)

and augment them with:
- **ICT/SMC** market-structure features
- **Volume profile** features

### Current state
- Universes exist and are auditable via `tvscreener-scan audit binance-universes`.
- Opportunity/strategy pipelines already support multi-timeframe scoring and matrix rendering.
- Lakehouse table isolation can be enabled via `TVSCREENER_LAKEHOUSE_LAYOUT=scalable`.

### Key decision
ICT/SMC and volume profile require OHLCV bar data; the current screener snapshot dataset alone is not sufficient.
So this proposal adds an explicit **market bars dataset** and then derives features from it.
