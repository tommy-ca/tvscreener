---
status: complete
priority: p2
issue_id: "084"
tags: [reliability, metadata, json]
dependencies: []
---

# Reliability: Metadata size limits

Implement size limits and truncation strategies for collected metadata to ensure the serialized JSON does not exceed 10MB.

## Problem Statement

The `MetadataCollector` currently collects all API calls and configuration details without any size enforcement. For very large scans (hundreds of symbols) or complex multi-step processes, the accumulated metadata could grow significantly. If the resulting JSON exceeds 10MB, it may cause failures in downstream systems, MCP agent responses, or database storage.

## Findings

- `tvscreener/lib/screeners/metadata_utils.py` manages metadata collection.
- `api_calls` is a list that grows with every call (lines 41, 55-76).
- `to_json()` (lines 103-105) serializes the entire dictionary without checks.
- There is no logic to cap the number of API calls or summarize them.

## Proposed Solutions

### Option 1: Cap and Summarize

**Approach:** Implement a maximum limit for `api_calls` (e.g., 50 calls). If exceeded, stop adding individual calls and instead increment a `dropped_calls_count` or provide a summarized view (e.g., "450 additional calls to TradingView API").

**Pros:**
- Simple to implement.
- Guarantees predictable memory and serialized size.
- Retains critical early metadata.

**Cons:**
- Loses individual call details for very large scans.

**Effort:** 1-2 hours

**Risk:** Low

---

### Option 2: Pre-serialization Size Check

**Approach:** In `to_json()`, check the size of the dictionary. If it exceeds a threshold, selectively drop the largest or least important fields (like full headers or long URL lists) until it fits.

**Pros:**
- Only acts when necessary.
- More flexible than a hard cap.

**Cons:**
- More complex to implement correctly.
- Performance overhead of size checking during serialization.

**Effort:** 2-3 hours

**Risk:** Medium

## Recommended Action

**To be filled during triage.**

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/metadata_utils.py`

## Acceptance Criteria

- [x] `MetadataCollector` has a configurable limit for the number of API calls recorded.
- [x] If the limit is reached, summary information is provided about missing calls.
- [x] `to_json()` (or a new `to_safe_json()`) verifies the output size is under 10MB.
- [x] Large metadata payloads are gracefully truncated/summarized.
- [x] Unit tests with simulated large metadata sets.

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Antigravity

**Actions:**
- Analyzed `metadata_utils.py` for size-related vulnerabilities.
- Identified potential for unbounded growth in `api_calls`.
- Proposed 10MB safety limit and truncation strategies.

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Implemented `max_api_calls` limit in `MetadataCollector`.
- Added `dropped_api_calls_count` to track missing calls.
- Updated `to_dict` to include `api_summary_stats`.
- Implemented size-safe `to_json` with multi-stage truncation (API calls, then config, then hard truncate).
- Updated `inspect_utils.py` to display dropped call counts.
- Added comprehensive unit tests in `tests/unit/test_metadata_limits.py`.
- Verified thread safety remains intact.

## Notes

- 10MB is a common limit for many internal messaging systems and agent protocols.
- Consider if specific fields (like `config`) also need length limits.
