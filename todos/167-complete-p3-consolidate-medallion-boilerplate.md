---
status: complete
priority: p3
issue_id: "167"
tags: [refactor, medallion, base]
dependencies: []
---

# Consolidate Medallion Stage Boilerplate

Extract shared stage handling logic in `base.py` into a reusable helper to reduce repetition across medallion runners.

## Problem Statement

Repetitive stage handling logic (checking for existing results, logging, and execution) is currently duplicated across various medallion stages in `base.py`. This leads to maintenance overhead and potential inconsistencies in how stages are resumed or run.

## Findings

- Multiple methods in `base.py` follow a similar pattern: check if a stage should be skipped/resumed, then run the stage logic, then handle the result.
- This boilerplate obscures the core logic of each stage.

## Proposed Solutions

### Option 1: Shared helper method

**Approach:** Extract a shared `_resume_or_run(stage_name, runner_func)` helper in the base medallion class.

**Pros:**
- Reduces code duplication.
- Centralizes stage execution logic (logging, error handling, result checking).
- Makes individual stage methods much cleaner.

**Cons:**
- Requires refactoring existing stage methods to use the helper.

**Effort:** 1-2 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `base.py`: Medallion base class.

## Acceptance Criteria

- [x] Shared `_resume_or_run` helper method implemented in `base.py`.
- [x] Existing medallion stages refactored to use the new helper.
- [x] All existing tests for medallion stages pass.
- [x] Logic for "resume" vs "run" remains consistent with previous implementation.

## Work Log

### 2026-03-02 - Initial Creation

**By:** Antigravity

**Actions:**
- Created P3 todo for medallion boilerplate consolidation.

### 2026-03-02 - Implementation

**By:** Antigravity

**Actions:**
- Extracted `_resume_or_run` in `base.py`.
- Refactored `_ingest`, `_standardize`, and `_score` to use the helper.
- Removed redundant Iceberg persistence from `_fetch_all_data`.
- Fixed duplicate `_merge_duplicates` method in `base.py`.
- Verified with new unit tests in `tests/unit/test_base_medallion.py`.

