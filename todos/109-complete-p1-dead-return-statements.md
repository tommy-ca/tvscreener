---
status: complete
priority: p1
issue_id: "109"
tags: [quality, dead-code, code-review]
dependencies: []
---

# Dead Code: Unreachable Return Statements

## Problem Statement

Two files have duplicate `return df` statements — the second is unreachable dead code. While not a runtime bug, this signals review oversight and could confuse maintainers.

## Findings

- `tvscreener/score.py:252-254` — Two consecutive `return df` in `calculate_confluence()`
- `tvscreener/lib/screeners/filter_utils.py:43-45` — `return df` after `return result.drop(...)` in `apply_ma_rating_filter()`

## Proposed Solutions

### Option 1: Delete Dead Lines

**Approach:** Remove line 254 from score.py and line 45 from filter_utils.py.

**Effort:** 2 minutes

**Risk:** None

## Recommended Action

**Delete dead lines.** Remove line 254 from `score.py` and line 45 from `filter_utils.py`. Trivial fix, no risk.

## Acceptance Criteria

- [ ] No unreachable code after return statements
- [ ] All tests still pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (performance-oracle, python-reviewer, code-simplicity-reviewer)

**Actions:**
- Three independent agents identified the same dead code
- Confirmed lines are unreachable via control flow analysis
