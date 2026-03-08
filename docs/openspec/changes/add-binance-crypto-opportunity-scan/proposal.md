## Proposal: Scan Binance crypto (spot + perps) via TradingView /scan with the shared opportunity scanner

### Context
The repo has a multi-asset screener framework and a shared **opportunity** scanner family.
Ingestion is TradingView `/scan`-based today, and the lakehouse schemas explicitly model TradingView screener snapshots.

### Goal
Enable scanning **Binance** crypto markets (as represented in TradingView) for:
- **Spot** and **perpetuals** (perps)
- **Universe**: top 100 by traded volume
- **Filters**:
  - 24h quote volume (USD) >= 10,000,000
  - 24h volatility >= 3%

Then run the shared opportunity analytics pipeline (rank/filter/matrix view) using the same runner + artifacts
contracts used for forex.

### Non-goals
- Implementing private Binance endpoints (no API keys)
- Building a new “binance” network connector in this phase
- Replacing TradingView as the default source
- Introducing a new workflow engine (Prefect is already the default runner)

### Key decisions
- The upstream API remains **TradingView `/scan`** (`source=tradingview`), filtered to `Exchange=BINANCE`.
- Spot vs perps are represented via TradingView `Type`:
  - spot: `Type=spot` (e.g. `BINANCE:BTCUSDT`)
  - perps: `Type=swap` (e.g. `BINANCE:BTCUSDT.P`)
- Universe membership is deterministic and persisted as an artifact for reproducibility.
