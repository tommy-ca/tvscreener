# Tasks: Binance crypto opportunity scan (TradingView /scan)

- [x] Add deterministic universe selector using TradingView crypto /scan (top 100, volume >= 10M, vol >= 3%)
- [x] Define `instrument_type` for crypto (`spot|perp`) derived from TradingView `Type` (`spot|swap`)
- [x] Extend `PipelineRunSpec` to carry `instrument_type` without overloading `contract_type`
- [ ] Update opportunity data pipeline to ingest Binance (TradingView-filtered) crypto snapshot rows to Bronze/Silver/Gold
- [ ] Update opportunity analytics pipeline to rank + render matrix for the Binance universe
- [ ] Persist `universe.json` artifact under `artifacts/runs/<params_hash>/`
- [x] Add batch template(s) under `workflows/prefect/batches/` for crypto spot/perps
- [ ] Add tests for universe determinism and artifacts contract
