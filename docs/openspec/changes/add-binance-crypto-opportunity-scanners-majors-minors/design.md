## Design: Crypto opportunity scanning (forex-parity)

### Default universes
Use `majors` as the default opportunity scan universe and `minors` for breadth.

Universe resolution (crypto):
- `--universe majors` + `--instrument-type spot` -> `binance_spot_majors`
- `--universe majors` + `--instrument-type perp` -> `binance_perp_majors`
- `--universe minors` + `--instrument-type spot` -> `binance_spot_minors`
- `--universe minors` + `--instrument-type perp` -> `binance_perp_minors`

### Pipeline modes
Match forex parity:
- `--pipeline both` for routine runs
- `--pipeline analytics` for fast rerenders from Iceberg

### Recommended presets

Spot majors (default):
```bash
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline both
```

Matrix view (analytics-only rerender):
```bash
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline analytics --matrix --limit 50
```

Run the same command for `instrument_type=perp` and/or `universe=minors`.

Perp majors (default):
```bash
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline both
```

Minors (breadth):
```bash
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline both
```

Note: strategy-specific volatility ranking/filtering is applied later in analytics; universes are liquidity + tradability focused.

### Strategy fit and risk notes

The crypto opportunity scanner is best aligned with:
- directional swing setups with multi-timeframe alignment
- momentum/trend continuation

Key risks to account for outside the scanner:
- funding / perp-specific microstructure
- broad risk regime (equities volatility spillover)

Recommended: pair crypto opportunity outputs with a macro risk overlay (e.g. NQ/ES/VIX/DXY) to modulate sizing and bias.

### Audit and readiness
Use the DuckDB review pipeline:

```bash
uv run tvscreener-scan review binance-universes --strict
```

Opportunity scans should prefer universes that are:
- quote-pure (USDT/USDC)
- base-deduped
- `is_opportunity_ready=True` in `## Scanner Readiness`

### Validation notes

Default workflow uses Prefect (`--runner prefect`) backed by a local Prefect server.

Local runner (`--runner local`) is an explicit fallback for debugging/offline runs; it executes through `PipelineRunSpec` and persists run metadata to `tvscreener.runs`.

Prefect server (local/dev):
```bash
export PREFECT_HOME="$PWD/.prefect-home"
uv run prefect server start --host 127.0.0.1 --port 4200 --background
export PREFECT_API_URL="http://127.0.0.1:4200/api"
```

Validate pipeline modes:
- Run `--pipeline data` then `--pipeline analytics` for the same universe.

Concurrency note (local/dev):
- When using the shared (legacy) Iceberg tables, avoid running multiple `--pipeline data` scans in parallel (they can conflict).
- Run spot/perp data scans sequentially, or use a scalable layout (`TVSCREENER_LAKEHOUSE_LAYOUT=scalable`) to isolate tables.

Quick Iceberg sanity checks:
```bash
uv run tvscreener-scan query tvscreener.signals_latest \
  --sql "SELECT asset_type, venue, count(*) AS n FROM df WHERE asset_type='crypto' GROUP BY 1,2"
```

### Review checklist (data + analytics)

1) Run data pipeline sequentially (legacy tables):
```bash
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline data --runner prefect
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline data --runner prefect
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline data --runner prefect
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --pipeline data --runner prefect
```

2) Verify Iceberg rows exist:
```bash
uv run tvscreener-scan query tvscreener.signals_latest \
  --sql "SELECT asset_type, count(*) AS n FROM df GROUP BY 1 ORDER BY n DESC"
```

3) Rerender matrix from Iceberg:
```bash
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline analytics --runner prefect --matrix --limit 50
```

Local fallback (same commands, explicit `--runner local`):
```bash
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline data --runner local
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline data --runner local
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline data --runner local
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --pipeline data --runner local

uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe majors --timeframes 240,60,15 --pipeline analytics --runner local --matrix --limit 50
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type perp --universe majors --timeframes 240,60,15 --pipeline analytics --runner local --matrix --limit 50
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type spot --universe minors --timeframes 240,60,15 --pipeline analytics --runner local --matrix --limit 50
uv run tvscreener-scan --scanner opportunity --asset-type crypto --instrument-type perp --universe minors --timeframes 240,60,15 --pipeline analytics --runner local --matrix --limit 50
```

If the universe returns fully-qualified symbols (e.g. `BINANCE:BTCUSDT`), analytics loads `signals_latest` by `entity_id`.

Matrix view displays a readable `PAIR` label derived from the crypto symbol (e.g., `BTCUSDT`).

Note: if `signals_latest.PAIR` is missing or null for crypto, the renderer fills it from the crypto `symbol`/`Symbol` with the venue prefix stripped.

Forex parity check:
- Run forex majors/minors with `--pipeline analytics --matrix` and confirm non-empty results.
- Run crypto majors/minors (spot/perp) and confirm non-empty results and non-null `PAIR` labels.

Matrix format:
- Crypto opportunity `--matrix` uses the same Confluence Matrix format as forex.

Matrix rendering stability:
- Factor columns reserve enough width so cells like `🟢|🟢|🟢` do not truncate into `🟢|🟢|…`.
- Prefect runner captures `matrix.txt` with a wide Rich console to keep artifacts stable for review.

Forex full-loop validation (data + analytics):
```bash
uv run tvscreener-scan --scanner opportunity --asset-type forex --universe majors --timeframes 240,60,15 --pipeline data --runner prefect
uv run tvscreener-scan --scanner opportunity --asset-type forex --universe majors --timeframes 240,60,15 --pipeline analytics --runner prefect --matrix
```

4) Audit universe readiness:
```bash
uv run tvscreener-scan review binance-universes --strict
```
