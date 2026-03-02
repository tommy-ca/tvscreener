---
status: completed
priority: p2
issue_id: "048"
tags: [kieran, types, code-review]
dependencies: []
---

# Problem Statement
In `risk_utils.py`, several parameters are typed as `float` but the code immediately checks if they `is None`. This is a type-hint mismatch; values that can be `None` must be typed with `| None` or `Optional`.

# Findings
- **File:** `tvscreener/lib/screeners/risk_utils.py`
- **Location:** `calculate_stop_loss` (atr), `calculate_take_profit` (stop_loss, entry), etc.

# Proposed Solutions
1. **Fix Type Union**: Change `float` to `float | None` for nullable parameters.

# Recommended Action
Correct the type hints in `risk_utils.py`.

# Acceptance Criteria
- [ ] Static analysis tools (mypy/pyright) no longer flag type mismatches in risk_utils.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified nullable type hint inconsistencies.
