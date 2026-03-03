---
status: completed
priority: p1
issue_id: "185"
tags: [security, path-traversal]
dependencies: []
---

# Remove Global Path Traversal Backdoor

## Problem Statement

Security risk: `util.py` disables `/tmp` path validation globally if `"pytest" in sys.modules`. This acts as a global backdoor for path traversal.

## Findings

- `util.py` currently checks `sys.modules` for the presence of `"pytest"`.
- If found, it disables path validation for `/tmp` paths globally.
- This creates a security risk where tests or mock environments might inadvertently mask path traversal vulnerabilities, or production code might act unexpectedly if pytest modules are somehow loaded.

## Proposed Solutions

### Option 1: Explicit Test Mode Parameter/Env Var

**Approach:** Remove the `sys.modules` check. Rely strictly on explicit `allow_tmp=True` parameters or dedicated `TVSCREENER_TEST_MODE` environment variables.

**Pros:**
- Completely removes the implicit global backdoor.
- Makes testing environment boundaries explicit, predictable, and safe.

**Cons:**
- May require updating several existing tests to explicitly pass the parameter or set the required environment variable.

**Effort:** 2-3 hours

**Risk:** Low

## Recommended Action

**To be filled during triage.** 
Remove the `pytest` module check in `util.py`. Implement explicit checking via `allow_tmp=True` arguments or `TVSCREENER_TEST_MODE` environment variables.

## Technical Details

**Affected files:**
- `util.py` (Path validation functions)
- Test suite files that relied on the implicit `/tmp` bypass.

## Acceptance Criteria

- [x] `sys.modules` check for `"pytest"` is completely removed from `util.py`.
- [x] Path validation for `/tmp` now relies strictly on the explicit `allow_tmp=True` parameter or the `TVSCREENER_TEST_MODE` environment variable.
- [x] All tests that previously relied on the global bypass are updated to use the explicit mechanisms (via `TVSCREENER_TEST_MODE` in `conftest.py`).
- [x] Verify the fix by running `uv run pytest` and confirming all tests pass securely.
- [x] Path traversal attempts into `/tmp` without explicit authorization successfully raise validation errors.

## Work Log

### 2026-03-03 - Initial Discovery

**By:** Opencode

**Actions:**
- Created P1 todo based on global path traversal backdoor finding in `util.py`.
- Specified standard env vars/parameters to replace the implicit test check.

### 2026-03-03 - Implementation

**By:** Opencode (AI)

**Actions:**
- Removed `sys.modules["pytest"]` and `sys.modules["unittest"]` checks from `validate_path` in `util.py`.
- Verified that `tests/conftest.py` already provides `TVSCREENER_TEST_MODE=1` which enables the `/tmp` bypass for all tests.
- Verified that all 272 tests pass.
- Verified that `validate_path` correctly blocks `/tmp` when neither `allow_tmp=True` nor `TVSCREENER_TEST_MODE=1` is set.

## Notes

- Important security fix to ensure test behavior mimics production behavior concerning file paths.
