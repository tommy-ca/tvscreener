---
status: complete
priority: p2
issue_id: "081"
tags: [performance, api, tradingview]
dependencies: []
---

# Base class fetches symbols individually

Refactor the base opportunity screener to fetch all symbols in a single batch request instead of iterating over symbols.

## Problem Statement

`BaseOpportunityScreener._fetch_all_data` currently uses a `ThreadPoolExecutor` to fetch data for each symbol individually. This results in one network request per symbol. TradingView's API supports filtering by a list of tickers (e.g., `set_tickers`), which allows fetching multiple symbols in a single high-performance batch call.

## Findings

- `tvscreener/lib/screeners/base.py:303-323` iterates over `self.symbols`.
- `_fetch_symbol_data` (lines 324-351) performs `screener.search(symbol)` and `screener.get()`.
- Each `get()` call triggers a POST request to TradingView.
- `ForexOpportunityScreener` already implements a batch-oriented `_fetch_all_data` (lines 108-164), demonstrating the approach.

## Proposed Solutions

### Option 1: Move Batch Logic to Base Class

**Approach:** Move the batch fetching logic from `ForexOpportunityScreener` into the `BaseOpportunityScreener` class. Use `screener.set_tickers(*symbols)` if symbols are provided.

**Pros:**
- Drastic reduction in network overhead and execution time.
- Standardizes batch fetching for all asset types.
- Simplifies subclasses.

**Cons:**
- Requires generic handling of ticker formatting (e.g., prefixing with exchange).
- May need batch partitioning if there's a limit on the number of tickers per request (usually 500-1000).

**Effort:** 3-4 hours

**Risk:** Medium (potential for API limit issues or malformed requests)

---

### Option 2: Optimize ThreadPool

**Approach:** Increase `max_workers` and optimize the individual calls.

**Pros:**
- Minimal architectural change.

**Cons:**
- Still inefficient compared to native batching.
- Higher risk of being rate-limited by TradingView.

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

Refactor to move batch logic to the base class (Option 1).

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/base.py`
- `tvscreener/lib/screeners/forex_opportunity.py` (to remove duplicate logic)
- `tvscreener/lib/screeners/crypto_opportunity.py` (if it exists or is added)

## Acceptance Criteria

- [x] `_fetch_all_data` in base class uses batch fetching by default.
- [x] Number of API calls reduced to 1 (or 1 per batch of ~500 symbols).
- [x] Subclasses no longer need to override `_fetch_all_data` for performance reasons.
- [x] Integration tests verify data is correctly fetched for multiple symbols.

## Work Log

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Refactored `BaseOpportunityScreener` in `base.py` to use batch fetching with `set_tickers`.
- Added `_get_tickers` and `_prepare_screener` hooks to the base class.
- Updated `_get_base_fields` in the base class to include more comprehensive fields.
- Refactored `ForexOpportunityScreener` in `forex_opportunity.py` to use the base class batching mechanism.
- Verified fix by running `tests/unit/test_forex_opportunity.py` and `tests/functional/test_forexscreener.py`.
- All tests passed.

### 2026-03-01 - Initial Discovery

**By:** Antigravity

**Actions:**
- Identified inefficient symbol-by-symbol fetching in `base.py`.
- Compared with `ForexOpportunityScreener` batch implementation.
- Analyzed TradingView API capabilities for ticker filtering.

## Notes

- Some assets might require different ticker formats (e.g., `BINANCE:BTCUSDT` vs `FX_IDC:EURUSD`). The base class should allow subclasses to provide a ticker formatter.
