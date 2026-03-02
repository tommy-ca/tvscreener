---
status: complete
priority: p2
issue_id: "058"
tags: [security, export, code-review]
dependencies: ["027"]
---

# Problem Statement
The XML export implementation relies on manual string concatenation and custom tag sanitization, which is inherently fragile and prone to edge-case failures or future injection vulnerabilities if the sanitization logic is modified incorrectly.

# Findings
- **File**: `tvscreener/lib/screeners/export_helpers.py`
- **Current Approach**: Uses a custom regex/isalnum check for keys and manual `fh.write(f"<{key}>")`.
- **Vulnerability**: While currently restrictive, manual XML building is a security anti-pattern.

# Proposed Solutions
1. **Full ElementTree implementation (Recommended)**: Construct the entire XML document (metadata + data) using `xml.etree.ElementTree`. This ensures correct nesting, encoding, and escaping automatically.

# Recommended Action
Refactor `export_to_xml` to use a standard library XML builder exclusively.

# Acceptance Criteria
- [x] XML export produces identical or improved valid XML.
- [x] No manual string interpolation for XML tags.
- [x] Handles nested dictionaries in metadata properly.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Security Sentinel)
- Flagged manual XML construction as a fragile anti-pattern.

### 2026-02-28 - Refactored to ElementTree
**By:** Antigravity
- Refactored `export_to_xml` to use `xml.etree.ElementTree`.
- Implemented recursive `_dict_to_xml` helper to handle nested metadata.
- Ensured valid XML structure with a single root element.
