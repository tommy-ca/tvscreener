---
status: complete
priority: p3
issue_id: "129"
tags: [quality, logging, code-review]
dependencies: []
---

# f-Strings in Logging Calls (13 Occurrences)

## Problem Statement

13 logging calls use f-strings (`logger.info(f"...")`) instead of lazy `%`-style formatting (`logger.info("%s", ...)`). f-strings are evaluated immediately even when log level is disabled.

## Findings

- `tvscreener/lib/screeners/base.py:105,210,280` — 3 occurrences
- `tvscreener/lib/orchestrator.py:653,661` — 2 occurrences
- `tvscreener/lib/screeners/export_helpers.py` — 8 occurrences

## Proposed Solutions

### Option 1: Convert to %-Style

**Approach:** Replace `logger.info(f"Scanning {x}")` with `logger.info("Scanning %s", x)`.

**Effort:** 15 minutes
**Risk:** None

## Recommended Action

**Convert to %-style.** Replace 13 `logger.info(f"...")` calls with `logger.info("%s", ...)` for lazy evaluation.

## Acceptance Criteria

- [ ] No f-strings in logging calls
- [ ] Logging output unchanged

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (kieran-python-reviewer)
