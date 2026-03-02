---
status: complete
priority: p2
issue_id: "046"
tags: [security, bug-fix, serialization]
dependencies: []
---

# Problem Statement
The sidecar `.meta.json` exporter uses `json.dump` without passing the custom `MetadataEncoder`. While the Parquet exporter uses it, the sidecar fallback will crash with a `TypeError` if the metadata contains non-standard objects (like `numpy.float64` from average scores or `datetime` objects).

# Findings
- **File:** `tvscreener/lib/screeners/export_helpers.py`
- **Location:** `_write_metadata_file`, `export_to_json`

# Proposed Solutions
1. **Use MetadataEncoder**: Pass `cls=MetadataEncoder` to the `json.dump` call.

# Recommended Action
Pass `cls=MetadataEncoder` in all `json.dump` calls within `export_helpers.py`.

# Acceptance Criteria
- [x] Exporting to CSV/JSON with metadata containing numpy types does not crash.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified sidecar JSON export crash on complex metadata types.

### 2026-02-28 - Resolved Crash
**By:** Antigravity (pr-comment-resolver)
- Added `MetadataEncoder` to all `json.dump` calls in `export_helpers.py`.
- Added `MetadataEncoder` to top-level imports in `export_helpers.py`.
