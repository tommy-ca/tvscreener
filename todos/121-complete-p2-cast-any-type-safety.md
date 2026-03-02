---
status: complete
priority: p2
issue_id: "121"
tags: [quality, typing, code-review]
dependencies: []
---

# cast(Any, ...) Defeats Type Safety for contract_type

## Problem Statement

`orchestrator.py:497,538` uses `cast(Any, request.contract_type or "cfd")` which tells mypy to skip type checking entirely. The root cause is `ScanRequest.contract_type` is `str | None` but configs expect `Literal["spot", "cfd", "spreadbet", "all"]`.

## Findings

- `tvscreener/lib/orchestrator.py:497` — `cast(Any, request.contract_type or "cfd")`
- `tvscreener/lib/orchestrator.py:538` — Same pattern
- Root cause: type mismatch between ScanRequest (str) and config (Literal)

## Proposed Solutions

### Option 1: Validate Before Passing

**Approach:** Check `contract_type` against valid values before passing to config.

**Effort:** 10 minutes
**Risk:** None

## Recommended Action

**Validate before passing.** Check `contract_type` against valid Literal values, raise a clear error on invalid input. Remove `cast(Any, ...)`.

## Acceptance Criteria

- [ ] No `cast(Any, ...)` in orchestrator
- [ ] Invalid contract_type raises clear error

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (kieran-python-reviewer)
