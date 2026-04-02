# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: CS momentum candidate universes

### Why a separate universe
Momentum strategies are sensitive to:
- stale/illiquid markets
- stablecoin pairs (low signal)
- wrapped/synthetic assets that behave differently than their underlyings

So we build a candidate universe that is already "tradeable" before ranking.

### Selection rules

Per instrument type (spot/perp):
1) Seed bases from TradingView top coins by market cap (`CoinScreener` `Market Cap Calc`, top 200).
2) Map to Binance tickers using `quote_assets` (default `USDT`, fallback `USDC`).
3) Drop missing tickers (not listed on Binance / not returned by TradingView).
4) Exclude bases in an explicit list (stablecoins, wrapped/synthetic).
5) Apply a liquidity gate (`Volume 24h in USD`):
   - spot default: `>= 1_700_000`
   - perp default: `>= 10_000_000`
6) Sort final list by `Volume 24h in USD` desc.

### Artifacts
Write `universe.json` under the run dir:
- seed bases (market cap)
- excluded bases
- requested tickers
- missing tickers
- final rows (ticker, entity_id, quote_volume_usd, volatility_24h_pct)
