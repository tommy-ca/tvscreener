---
status: complete
priority: p3
issue_id: "130"
tags: [quality, hygiene, code-review]
dependencies: []
---

# Root-Level Scratch Test Files Tracked in Git

## Problem Statement

`test_duckdb.py` (27 lines) and `test_duckdb_sandbox.py` (46 lines) are tracked in git but are one-off experiment scripts, not proper tests. They belong in `tests/` or should be removed.

## Findings

- `test_duckdb.py` — Tracked, 27 lines, sandbox benchmark script
- `test_duckdb_sandbox.py` — Tracked, 46 lines, sandbox escape testing
- `test_duckdb_config.py` and `test_duckdb_pragma.py` — Untracked (not in git)
- `debug*.py` — Already in .gitignore

## Proposed Solutions

### Option 1: git rm + .gitignore

**Approach:** `git rm` both files. Add `test_duckdb*.py` to root .gitignore.

**Effort:** 2 minutes
**Risk:** None

## Recommended Action

**git rm + .gitignore.** Remove both files from git, add `test_duckdb*.py` to root .gitignore.

## Acceptance Criteria

- [ ] No scratch test files at project root tracked in git
- [ ] .gitignore prevents re-addition

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (code-simplicity-reviewer)
