---
status: complete
priority: p1
issue_id: "089"
tags: [hygiene, git]
dependencies: []
---

# Repository Hygiene: pycache and .gitignore

__pycache__ files are currently tracked in git due to an overly broad negative ignore pattern.

## Problem Statement

`__pycache__` files and `.pyc` files are being tracked in the repository. This causes unnecessary noise in git status and diffs, and can lead to merge conflicts or environment-specific issues being committed.

## Findings

- Git status shows many `.pyc` files and `__pycache__` directories being tracked.
- `.gitignore` contains a pattern `!/tvscreener/lib/**` which is overly broad. This negative ignore (whitelist) pattern overrides generic ignores for any files within that directory structure, including Python bytecode caches.

## Proposed Solutions

### Option 1: Fix .gitignore and Clean Index

**Approach:** 
1. Update `.gitignore` to ensure `__pycache__` and `.pyc` are always ignored, even inside whitelisted directories. 
2. Remove existing cache files from the git index using `git rm --cached`.

**Pros:**
- Permanently solves the issue.
- Cleans up the current repository state.
- Prevents future accidental commits of bytecode.

**Cons:**
- Requires a commit that might touch many files (deletions from index).

**Effort:** 30 minutes

**Risk:** Low

## Recommended Action

**To be filled during triage.** Clear, actionable plan for resolving this todo.

## Technical Details

**Affected files:**
- `.gitignore`
- Multiple `__pycache__` directories and `.pyc` files across the project.

## Acceptance Criteria

- [x] No `.pyc` files or `__pycache__` directories are tracked by git (`git ls-files | grep pyc` returns empty).
- [x] `.gitignore` is modified to prevent `__pycache__` from being tracked even in whitelisted paths.
- [x] `git status` is clean of bytecode files.

## Work Log

### 2026-03-01 - Initial Discovery

**By:** opencode

**Actions:**
- Identified tracking of `__pycache__` files.
- Traced cause to broad negative ignore pattern in `.gitignore`.
- Created this todo to track resolution.

**Learnings:**
- Negative ignore patterns (`!`) in `.gitignore` can have unintended side effects if not scoped tightly enough.

### 2026-03-01 - Resolved

**By:** pr-comment-resolver

**Actions:**
- Updated `.gitignore` to move bytecode ignore patterns after the `!/tvscreener/lib/**` whitelist.
- Ran `git rm -r --cached` to remove tracked `__pycache__` directories and `.pyc` files.
- Verified removal with `git ls-files | grep pyc`.
- Renamed todo to `089-complete-...`.
