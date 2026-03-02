---
status: complete
priority: p2
issue_id: "113"
tags: [security, path-validation, code-review]
dependencies: []
---

# allow_tmp=True Hardcoded in All Production Code Paths

## Problem Statement

Every `validate_path()` call site passes `allow_tmp=True`. The `sys.modules` test guard is weak — if any dependency imports `unittest` transitively, the guard fails in production.

## Findings

- `tvscreener/lib/orchestrator.py:633` — `validate_path(path_str, allow_tmp=True)`
- `tvscreener/lib/screeners/base.py:103` — `validate_path(path, allow_tmp=True)`
- `tvscreener/config/loader.py:18` — `validate_path(path, allow_tmp=True)`
- `/tmp` is world-writable, enabling symlink attacks

## Proposed Solutions

### Option 1: Remove allow_tmp from Production Paths

**Approach:** Only pass `allow_tmp=True` in test fixtures via conftest.py.

**Effort:** 15 minutes
**Risk:** Low

## Recommended Action

**Remove allow_tmp from production paths.** Only pass `allow_tmp=True` in test fixtures via conftest.py. Production code should use configured output directories only.

## Acceptance Criteria

- [ ] Production code paths do not pass `allow_tmp=True`
- [ ] Test fixtures explicitly enable tmp access
- [ ] Tests still pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (security-sentinel)
