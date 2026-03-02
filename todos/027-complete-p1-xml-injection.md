---
status: completed
priority: p1
issue_id: "027"
tags: [security, export, xml]
dependencies: []
---

# Fix XML Injection in Export Helpers

## Problem Statement

Metadata written to XML export files is not escaped, allowing XML injection attacks and broken XML output when metadata contains special characters like `>`, `<`, `&`.

## Findings

- **Location:** `tvscreener/lib/screeners/export_helpers.py:101-104`
- **Issue:** Direct string interpolation writes metadata without escaping
- **Code:**
  ```python
  fh.write(f"  <{key}>{value}</{key}>\n")  # No escaping!
  ```
- **Impact:** XXE attacks, XSS in downstream consumers, broken XML output

## Proposed Solutions

### Option 1: Use xml.sax.saxutils.escape

**Approach:** Import and use `xml.sax.saxutils.escape` for all metadata values.

**Pros:**
- Simple one-line fix
- Standard library, no dependencies
- Handles all XML special characters

**Cons:**
- Must convert values to string first

**Effort:** 10 minutes

**Risk:** Low

---

### Option 2: Use xml.etree.ElementTree

**Approach:** Build XML tree properly using ET, which auto-escapes.

**Pros:**
- More robust XML handling
- Auto-escapes special characters

**Cons:**
- More code change
- Slightly different output format

**Effort:** 30 minutes

**Risk:** Low

---

## Recommended Action

[To be filled during triage]

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/export_helpers.py:101-104`

## Acceptance Criteria

- [x] XML export escapes special characters
- [x] Metadata with `>`, `<`, `&` produces valid XML
- [x] Tests added for XML injection scenarios

## Work Log

### 2026-02-28 - Fix Implemented

**By:** Antigravity

**Actions:**
- Used `xml.sax.saxutils.escape` to escape metadata values.
- Implemented key sanitization to ensure valid XML tag names.
- Switched to `etree` parser and `xml_declaration=False` in `to_xml` to avoid issues with file handles and ensure valid XML when combined with metadata.
- Added unit tests in `tests/unit/test_export_helpers.py` verifying both value escaping and key sanitization.
- Verified that the resulting XML is valid and safe from injection.

### 2026-02-25 - Security Review Discovery

**By:** Claude Code (Security Sentinel)

**Actions:**
- Identified XML injection vulnerability during code review
- Found location in export_helpers.py

**Learnings:**
- All user-supplied data in metadata could be exploited
