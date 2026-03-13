# Tasks: Binance crypto opportunity scan (TradingView /scan)

- [x] Add deterministic universe selector using TradingView crypto /scan (top 100 by volume; liquidity + exclusions + dedup)
- [x] Persist diagnostics in `universe.json` for top100 underfill analysis
- [x] Restrict `binance_{spot,perp}_top100` to `USDT`/`USDC` quotes
- [ ] Add market cap top100 selector (CoinScreener Market Cap Calc -> Binance USDT markets)
- [x] Add market cap top100 selector (CoinScreener Market Cap Calc -> Binance USDT markets)
- [ ] Add DuckDB analytics query templates to filter by volume/volatility and render matrix
- [x] Define `instrument_type` for crypto (`spot|perp`) derived from TradingView `Type` (`spot|swap`)
- [x] Extend `PipelineRunSpec` to carry `instrument_type` without overloading `contract_type`
- [ ] Update opportunity data pipeline to ingest Binance (TradingView-filtered) crypto snapshot rows to Bronze/Silver/Gold
- [ ] Update opportunity analytics pipeline to rank + render matrix for the Binance universe
- [ ] Persist `universe.json` artifact under `artifacts/runs/<params_hash>/`
- [x] Add batch template(s) under `workflows/prefect/batches/` for crypto spot/perps
- [x] Freeze universe selection into `run_spec.json` for deterministic analytics reruns
- [x] Persist `universe.json` under `artifacts/runs/<params_hash>/` with `entity_id` + `symbol`
- [ ] Add tests for universe determinism and artifacts contract
