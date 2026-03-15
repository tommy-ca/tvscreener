## Design: Market risk scanner (opportunity matrix)

### What this scanner is

This is **not** a trade universe. It is a **risk regime overlay**.

It scans a small macro basket using the same factor confluence model as the opportunity scanner:
- `TREND`, `MA`, `OSC`, `ROC` across timeframes
- Grid alignment (`GRID_ALIGNED/GRID_TOTAL`) and grade

### Basket definition

The basket should be small, stable, and globally meaningful.

In TradingView, these instruments are not all available from a single screener endpoint, so the **market risk overlay** is implemented as a *bundle* of opportunity scans:

Futures risk (risk-on/off):
- `asset_type=futures`: `CME_MINI:ES1!`, `CME_MINI:NQ1!`, `CBOE:VX1!`

USD macro (tightening/loose USD):
- `asset_type=stock`: `TVC:DXY`

Notes:
- Prefer continuous futures (e.g., `ES1!`) for stable history.
- `CBOE:VX1!` is the VIX futures continuous symbol on the futures endpoint.

### Validation findings (data vs matrix)

Observed with `CME_MINI:ES1!`, `CME_MINI:NQ1!`, `CBOE:VX1!` on the futures endpoint:
- Timed opportunity factors (`Recommend.*|{tf}`, `Roc|{tf}`) are returned as null/NA.
- This yields an all-neutral matrix (`⚪|⚪|⚪`, `0/12`, `Grade=F`) even though the tickers ingest successfully.

Implication:
- For a meaningful matrix-based overlay, prefer **risk proxies that populate the opportunity factor columns**.

Recommended proxy mapping (matrix-friendly):
- NQ proxy: `NASDAQ:QQQ` (stock)
- ES proxy: `AMEX:SPY` (stock)
- VIX: `TVC:VIX` (stock)
- DXY: `TVC:DXY` (stock)

Named universe:
- Use `--asset-type stock --universe market_risk` to run the proxy basket without passing `--pairs`.

Validated run artifacts (Prefect):
- `artifacts/runs/24124097f596691e0f78e9c7b9e3871d2d16bfef3d522308b7ac457de011e0a6/matrix.txt`

### Strategy fit (how to interpret results)

This output is best used to **adjust risk and bias** for other scanners:

- Forex majors/minors opportunities:
  - If DXY is strongly bullish across timeframes, be cautious with long EURUSD/GBPUSD/AUDUSD/NZDUSD setups.
- Crypto opportunities:
  - If NQ/ES trend/momentum are bearish and VIX is bullish, treat crypto long signals as higher-risk (reduce size, demand higher confluence).

The market risk scanner is most compatible with:
- trend-following / momentum continuation
- swing entries with multi-timeframe alignment

It is least compatible with:
- pure mean-reversion systems without regime filtering

### Pipeline workflow (Prefect default)

Because the current (legacy) Iceberg tables are shared/overwritten per run, either:
- run `data` then `analytics` immediately for each scan, or
- use `TVSCREENER_LAKEHOUSE_LAYOUT=scalable` to isolate tables per asset/universe.

Prefect server:
```bash
export PREFECT_HOME="$PWD/.prefect-home"
uv run prefect server start --host 127.0.0.1 --port 4200 --background
export PREFECT_API_URL="http://127.0.0.1:4200/api"
```

Futures risk scan:
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type futures \
  --pairs CME_MINI:ES1! CME_MINI:NQ1! CBOE:VX1! \
  --timeframes 240,60,15 --pipeline data

uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type futures \
  --pairs CME_MINI:ES1! CME_MINI:NQ1! CBOE:VX1! \
  --timeframes 240,60,15 --pipeline analytics --matrix --limit 10
```

DXY scan:
```bash
uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type stock \
  --pairs TVC:DXY \
  --timeframes 240,60,15 --pipeline data

uv run tvscreener-scan --runner prefect --scanner opportunity --asset-type stock \
  --pairs TVC:DXY \
  --timeframes 240,60,15 --pipeline analytics --matrix --limit 10
```

### Market risk heuristics (operator-facing)

These are *interpretation rules*, not hard filters:

- **Risk-on**: NQ and ES mostly bullish, VIX mostly bearish
- **Risk-off**: VIX bullish and NQ/ES bearish, especially at 240/60
- **USD tightening**: DXY bullish with strong ROC/MA alignment
