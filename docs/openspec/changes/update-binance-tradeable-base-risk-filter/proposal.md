# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Proposal: Filter out new, risky tickers from Binance tradeable universes

### Goal
Reduce strategy-universe churn by excluding "new but liquid" assets that have too little trading history.

### Definition (risky)
An asset is considered risky when:
- it is included in `binance_{spot,perp}_tradeable_base` due to volume gates, AND
- its base is not present in the market-cap top100 reference (`binance_{spot,perp}_mcap_top100` bases), AND
- its TradingView bar history length is below a configured threshold.

### Approach
- Add a selection-time filter to `binance_{spot,perp}_tradeable_base`:
  - compute `history_days` from TradingView `First Bar Time` and `Last Bar Update Time`
  - exclude non-mcap-top100 bases where `history_days < min_history_days_non_mcap`
- Persist `history_days` and `excluded_risky` in `universe.json` for auditability.
