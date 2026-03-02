---
status: completed
priority: p1
issue_id: "044"
tags: [kieran, quality, code-review]
dependencies: []
---

# Problem Statement
`_fetch_pair_data` catches the base `Exception` class and returns an empty DataFrame. This silent failure masks true programming bugs (like `TypeError` or `AttributeError`) by passing them off as "API fetching errors." This makes the code difficult to debug as internal crashes are swallowed.

# Findings
- **File:** `tvscreener/lib/screeners/forex_opportunity.py`
- **Location:** `_fetch_pair_data`
- **Evidence:**
  ```python
  except Exception as e:
      logger.error(f"Error fetching {pair}: {e}")
      return pd.DataFrame()
  ```

# Proposed Solutions
1. **Catch Specific Errors (Recommended)**: Catch only expected network errors (e.g., `requests.RequestException`). Let other exceptions bubble up.
2. **Re-raise on Debug**: Add a flag to re-raise exceptions in test/debug mode.

# Recommended Action
Implement Solution 1: Restrict the try/except block to specific network and API-related exceptions.

# Acceptance Criteria
- [x] Code bugs (NameError, TypeError) cause a loud failure and stack trace.
- [x] Network timeouts or 404s still return an empty DataFrame gracefully.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified anti-pattern of bare exception catching.

### 2026-02-28 - Resolution
- Restricted `_fetch_pair_data` to catch only `MalformedRequestException`.
- Removed generic `Exception` catch from `get_opportunities` to allow programming bugs to bubble up.
- Verified with unit tests that bugs (e.g., `TypeError`) cause loud failures while API errors are handled gracefully.
