---
status: completed
priority: p1
issue_id: "055"
tags: [performance, api, code-review]
dependencies: []
---

# Problem Statement
The `ForexOpportunityScreener` uses a `ThreadPoolExecutor` to fetch data for each pair individually. For a universe of 27 pairs, it makes 27 separate HTTP requests. This is highly inefficient as the TradingView API supports batching multiple symbols into a single request.

# Findings
- **File**: `tvscreener/lib/screeners/forex_opportunity.py`
- **Lines**: 111-118 (approx)
- **Evidence**:
  ```python
  futures = {executor.submit(self._fetch_pair_data, pair): pair for pair in self.pairs}
  ```

# Proposed Solutions
1. **Batch Request (Recommended)**: Refactor `get_opportunities` to collect all pairs and make **one** call to the `ForexScreener` with the `tickers` payload.
2. **Chunked Batches**: If the universe is massive (>1000), fetch in chunks of 500.

# Recommended Action
Implement Solution 1: Use a single batch API call for the entire pair list.

# Acceptance Criteria
- [x] Scan for 27 pairs results in 1 (or very few) API calls instead of 27.
- [x] Total scan time for "all" universe is significantly reduced.
- [x] Metadata correctly reflects the batch call.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Performance Oracle)
- Identified sequential/threaded per-pair API overhead.

### 2026-02-28 - Implemented Batch API Call
**By:** Antigravity
- Added `set_tickers` method to `Screener` base class to support batching.
- Refactored `ForexOpportunityScreener` to use `set_tickers` with all preferred exchange/pair combinations in a single `_fetch_all_data` call.
- Verified that a scan with multiple pairs now results in exactly one API call.
- Fixed `MetadataCollector` and example script issues found during verification.
