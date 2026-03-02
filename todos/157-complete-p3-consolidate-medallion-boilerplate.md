---
status: complete
priority: p3
issue_id: "157"
tags: [refactor, medallion, base-py]
dependencies: []
---

# Consolidate Medallion Stage Boilerplate

Extract a shared `_resume_or_run(stage_name, runner_func)` helper to handle repetitive Loading/Resuming logic.

## Problem Statement

The `base.py` file contains repetitive `try/except` blocks across the three medallion stages (Bronze, Silver, Gold) for handling "Loading" and "Resuming" states. This redundancy increases maintenance overhead and potential for inconsistent state management across stages.

## Findings

- Repetitive `try/except` for Loading/Resuming across three stages in `base.py`.
- The pattern involves checking if a stage can be resumed, and if not, performing a full load.
- Common boilerplate includes logging, exception handling, and potentially state updates that are mirrored in each stage's execution method.

## Proposed Solutions

### Option 1: Shared Helper in Base Class

**Approach:** Implement a private method `_resume_or_run(stage_name, runner_func)` in the base class.

**Pros:**
- Eliminates code duplication.
- Standardizes error handling and logging for all stages.
- Easier to add common features (e.g., telemetry, retry logic) to all stages at once.

**Cons:**
- Requires careful design of the `runner_func` signature to accommodate different stage requirements.

**Effort:** 1-2 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/base.py` - Contains the medallion stage execution logic.

## Acceptance Criteria

- [ ] Private method `_resume_or_run` created in `base.py`.
- [ ] Bronze, Silver, and Gold stage execution methods refactored to use `_resume_or_run`.
- [ ] Logic for "Resuming" vs "Loading" remains functionally identical to current implementation.
- [ ] All tests pass, ensuring no regressions in stage transition or error recovery.

## Work Log

### 2026-03-02 - Task Creation

**By:** Antigravity

**Actions:**
- Identified repetitive pattern in `base.py` medallion stages.
- Proposed consolidation via `_resume_or_run` helper.
- Created P3 todo.

## Notes

- Nice-to-have refactor for better maintainability.
