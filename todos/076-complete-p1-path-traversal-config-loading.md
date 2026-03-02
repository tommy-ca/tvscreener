---
status: complete
priority: p1
issue_id: "076"
tags: [security, config]
dependencies: []
---

# Path traversal in config loading

Fix path traversal vulnerability in configuration loading logic.

## Problem Statement

The application's configuration loading mechanism is vulnerable to path traversal attacks, potentially allowing an attacker to read arbitrary files from the filesystem.

## Findings

- Vulnerability identified in `tvscreener/config/loader.py` and `tvscreener/lib/orchestrator.py`.
- Severity: High

## Proposed Solutions

### Option 1: Strict Path Validation

**Approach:** Implement robust path validation using `os.path.abspath` and checking that the resulting path is within the intended configuration directory.

**Pros:**
- Effectively prevents traversal outside authorized directories.
- Minimal performance impact.

**Cons:**
- Requires careful implementation to handle all edge cases.

**Effort:** 1-2 hours

**Risk:** Low

## Recommended Action

**Unified Path Validation:** Implement a centralized `validate_path` utility and use it consistently across all configuration loading and saving entry points in `loader.py` and `orchestrator.py`.

## Technical Details

**Affected files:**
- `tvscreener/config/loader.py`
- `tvscreener/lib/orchestrator.py`

## Acceptance Criteria

- [x] Path traversal vulnerability is mitigated in `loader.py` and `orchestrator.py`.
- [x] Tests verify that traversal attempts (e.g., using `../`) are rejected.
- [x] Configuration loading still works for valid paths.

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Antigravity

**Actions:**
- Identified path traversal vulnerability in config loading.
- Created todo item for tracking.

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Verified that `tvscreener/util.py` contains a robust `validate_path` function.
- Updated `tvscreener/config/loader.py` to use `validate_path` for YAML configuration loading with improved error reporting.
- Updated `tvscreener/lib/orchestrator.py` to centralize validation in a new `ScreenerController._validate_path` method (to satisfy existing tests).
- Applied unified validation to all path-related operations in `ScreenerController` (output export, parquet inspection, and config saving).
- Proactively secured `tvscreener/mcp/tools.py` configuration loading/saving entry points.
- Verified that `validate_path` handles absolute paths, relative paths, and symlinks correctly via `resolve()`.

## Notes

- Critical security fix.
- Centralized validation ensures consistency and makes it easier to update security policies globally.
- `allow_tmp=True` is used to maintain compatibility with tests that use temporary directories, but it is gated by an environment check in `validate_path`.
