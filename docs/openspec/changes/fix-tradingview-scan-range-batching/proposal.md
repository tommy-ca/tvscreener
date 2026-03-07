# Change: Fix TradingView scan batching (range must cover tickers)

## Why
TradingView `/scan` responses honor the request `range` even when `symbols.tickers` is explicitly provided.

Today, `Screener` defaults to `range=[0,150]`, which causes silent truncation when we batch more than 150 tickers per
request (e.g., forex exchange × pairs, multi-asset universes, or Prefect-sharded batches).

This blocks safe, scalable multi-asset / multi-timeframe scanning because results can be dropped without errors.

## What changes
- When `symbols.tickers` is provided and the range is still the default, automatically set request range to cover all
  requested tickers: `range=[0,len(tickers)]`.
- Add a regression test that validates the outgoing payload range is sized correctly for tickers.

## Non-goals
- Change paging behavior for market-wide scans using `symbols.query` (no tickers list).
- Change the existing batch sizing logic (still chunk tickers; this change prevents truncation inside each chunk).

## Impact
- Enables “scan many symbols at once” efficiently by ensuring batched requests return all tickers in the batch.
- Reduces the number of API calls needed for multi-asset scanning (bounded by batch size and timeframe sets).

