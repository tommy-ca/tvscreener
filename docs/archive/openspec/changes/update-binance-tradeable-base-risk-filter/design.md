# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: New, risky asset filter

### Why
Tradeable universes are volume-gated, so newly listed meme/launch assets can enter quickly.
For strategy research (TS/CS momentum/MR), these assets add operational risk:
- short data history (signals unstable)
- universe churn
- inconsistent spot/perp availability

### Inputs
From TradingView crypto `/scan` rows:
- `First Bar Time`
- `Last Bar Update Time`
- `Volume 24h in USD`

Reference anchor:
- market-cap top100 bases from CoinScreener (same source used by `*_mcap_top100` universes)

### Filter rule
For `binance_{spot,perp}_tradeable_base`:
- compute `history_days = (last_bar_update_time - first_bar_time) / 86400`
- if `base` is NOT in market-cap top100 and `history_days < min_history_days_non_mcap`, exclude

### Artifacts
`universe.json` rows include `history_days`.
`universe.json` includes `excluded_risky` (a capped list of excluded rows with reason inputs).
