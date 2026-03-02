---
status: completed
priority: p1
issue_id: "052"
tags: [security, cli, code-review]
dependencies: []
---

# Problem Statement
The `_validate_path` function in `cli.py` contains a fragile security bypass that allows arbitrary file writes to `/tmp/` if `pytest` is detected in `sys.modules`. This is unsafe as many production environments include testing libraries, and an attacker could potentially exploit this to write malicious files to shared temporary directories.

# Findings
- **File**: `tvscreener/cli.py`
- **Evidence**:
  ```python
  import sys
  if "/tmp/" in str(resolved_path) and "pytest" in sys.modules:
      return resolved_path
  ```

# Proposed Solutions
1. **Remove Bypass (Recommended)**: Remove the `sys.modules` check. Use a dedicated environment variable (e.g., `TVSCREENER_TEST_MODE`) or a specialized `base_dir` parameter for tests that explicitly allows a temporary path.
2. **Strict Limit**: If a bypass is needed, limit it to a very specific sub-directory of `/tmp/` that is unique to the current user or process.

# Recommended Action
Implement Solution 1: Use an environment variable or a `base_dir` argument to allow testing paths without opening a hole in production logic.

# Acceptance Criteria
- [x] Path validation does not depend on `sys.modules["pytest"]`.
- [x] Traversal to `/tmp/` is blocked by default in production.
- [x] Security tests still pass using the new authorized bypass mechanism.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Security Sentinel)
- Identified fragile security bypass in path validation.

### 2026-02-28 - Resolution
**By:** Antigravity
- Removed `sys.modules["pytest"]` check in `_validate_path`.
- Implemented environment variable `TVSCREENER_TEST_MODE` check to allow `/tmp/` access during tests.
- Added `tests/conftest.py` to automatically set `TVSCREENER_TEST_MODE=1` for all tests.
