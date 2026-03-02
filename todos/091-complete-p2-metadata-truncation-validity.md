---
status: completed
priority: p2
issue_id: "091"
tags: [reliability, metadata]
dependencies: []
---

# Metadata Truncation Validity

MetadataCollector.to_json hard-truncates strings if they exceed size limit, resulting in invalid JSON.

## Problem Statement

The `MetadataCollector.to_json` method currently performs a hard truncation on strings that exceed a specific size limit. This truncation can occur in the middle of a JSON string, leading to malformed and invalid JSON output which causes parsing errors downstream.

## Findings

- Located in `metadata_utils.py` around line 105.
- The current implementation likely uses a simple string slice (e.g., `s[:limit]`) when the size exceeds the threshold.
- This results in invalid JSON if the truncation happens inside a key, value, or structural character.

## Proposed Solutions

### Option 1: Return Error JSON (IMPLEMENTED)

**Approach:** If the serialized JSON exceeds the size limit, catch the condition and return a predefined valid JSON object indicating a "size limit exceeded" error.

**Pros:**
- Always returns valid JSON.
- Clearly communicates the failure to consumers.
- Simple to implement.

**Cons:**
- Original data is lost.

**Effort:** 1 hour

**Risk:** Low

---

### Option 2: Selective Truncation of Values

**Approach:** Instead of truncating the final JSON string, truncate individual large string values within the dictionary before serialization, while keeping the JSON structure intact.

**Pros:**
- Preserves as much valid metadata as possible.
- Returns valid JSON.

**Cons:**
- More complex to implement (requires traversing the structure).
- Might still exceed limits if there are many small keys.

**Effort:** 3-4 hours

**Risk:** Medium

## Recommended Action

Implemented Option 1 as requested.

## Technical Details

**Affected files:**
- `metadata_utils.py` (Line ~105)

## Acceptance Criteria

- [x] `to_json` always returns valid JSON.
- [x] If size limit is exceeded, a specific error or valid error JSON is produced instead of a truncated string.
- [x] Unit tests verify behavior with payloads exceeding the limit.

## Work Log

### 2026-03-01 - Initial Todo Creation

**By:** opencode

**Actions:**
- Created todo based on user request for issue 091.
- Identified problem location in `metadata_utils.py`.
- Proposed two solutions: returning error JSON or selective value truncation.

### 2026-03-01 - Implemented Error JSON Response

**By:** gemini-3-flash-preview

**Actions:**
- Modified `MetadataCollector.to_json` in `tvscreener/lib/screeners/metadata_utils.py` to return `{"error": "metadata_too_large"}` instead of a truncated string.
- Updated unit test `test_metadata_hard_truncation_safety` in `tests/unit/test_metadata_limits.py` to verify valid JSON error response.
- Verified all tests pass.

