---
status: completed
priority: p1
issue_id: "039"
tags: [security, code-review]
dependencies: []
---

# Problem Statement
The `MetadataCollector` explicitly whitelists any header starting with `X-TV-`. TradingView authentication tokens and session IDs use this prefix (e.g., `X-TV-Token`, `X-TV-Session-Id`). This will embed users' secrets in plaintext directly into exported files (CSV, JSON, Parquet, XML) and sidecar files.

# Findings
- **File:** `tvscreener/lib/screeners/metadata_utils.py`
- **Location:** `MetadataCollector.add_api_call`
- **Evidence:**
  ```python
  sanitized_headers = {
      k: v
      for k, v in headers.items()
      if k in self.HEADER_WHITELIST or k.startswith("X-TV-")
  }
  ```

# Proposed Solutions
1. **Strict Whitelist (Recommended)**: Remove the `startswith("X-TV-")` catch-all and only whitelist specific, known-safe `X-TV-` headers.
2. **Blacklist Secrets**: Keep the catch-all but explicitly filter out keys containing "Token", "Session", "Auth", or "Key".

# Recommended Action
Implement Solution 1: Use a strict whitelist for standard non-sensitive headers only.

# Acceptance Criteria
- [x] `X-TV-Token` and similar sensitive headers are not present in exported metadata.
- [x] Only explicitly whitelisted headers are exported.
- [x] Unit test verifies sanitization of sensitive headers.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified security leak in MetadataCollector header sanitization.

### 2026-02-28 - Fixed
**By:** Antigravity
- Implemented strict whitelist in `MetadataCollector.add_api_call`.
- Added regression test in `tests/unit/test_inspect.py`.
- Verified fix with tests.
