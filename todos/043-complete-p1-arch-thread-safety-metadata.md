---
status: completed
priority: p1
issue_id: "043"
tags: [architecture, concurrency, code-review]
dependencies: []
---

# Problem Statement
`ForexOpportunityScreener.get_opportunities` uses a `ThreadPoolExecutor` to fetch pair data concurrently. Inside the threaded workers, it calls `self.metadata.add_api_call(...)` which appends to a shared list. While `list.append` is currently thread-safe in CPython (due to the GIL), it is an implementation detail that will break in PEP 703 (Free-threaded Python) and is considered bad practice.

# Findings
- **File:** `tvscreener/lib/screeners/forex_opportunity.py`
- **Call-site:** `_fetch_pair_data` -> `self.metadata.add_api_call`
- **Resource:** `MetadataCollector.api_calls` (list)

# Proposed Solutions
1. **Thread-safe Lock (Recommended)**: Add a `threading.Lock` to the `MetadataCollector` and wrap the append operation.
2. **Thread-local storage**: Use thread-local storage and aggregate after join.

# Recommended Action
Implement Solution 1: Add a mutex lock to `MetadataCollector`.

# Acceptance Criteria
- [x] `MetadataCollector` uses a lock for any mutation of shared state.
- [x] Threaded scans remain performant.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified race condition risk in multi-threaded metadata collection.

### 2026-02-28 - Implemented Thread Safety
**By:** Antigravity
- Added `threading.Lock` to `MetadataCollector`.
- Protected `set_config`, `add_api_call`, `finish`, and `to_dict` with the lock.
- Verified with unit tests in `tests/unit/test_metadata_thread_safety.py`.
