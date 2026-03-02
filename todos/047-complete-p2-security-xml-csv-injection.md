---
status: complete
priority: p2
issue_id: "047"
tags: [security, quality, code-review]
dependencies: []
---

# Problem Statement
XML and CSV exports contain injection vulnerabilities. XML is built using raw f-strings without escaping special characters (leading to malformed files or injection). CSV metadata is written as `# {value}` which allows a value with a newline (`\n`) to inject arbitrary data rows into the CSV.

# Findings
- **File:** `tvscreener/lib/screeners/export_helpers.py`
- **Location:** `export_to_xml`, `export_to_csv`

# Proposed Solutions
1. **Standard Libraries**: Use `xml.etree.ElementTree` for XML.
2. **Sanitize CSV Metadata**: Strip newlines from metadata values before writing them as comments.

# Recommended Action
Refactor XML export to use a proper builder and sanitize CSV comment strings.

# Acceptance Criteria
- [x] Metadata values with `<` or `&` produce valid XML.
- [x] Metadata values with newlines do not create new rows in CSV.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified XML/CSV injection risks in export formatting.

### 2026-02-28 - Sanitized CSV Metadata
**By:** Antigravity (pr-comment-resolver)
- Added newline stripping to CSV metadata comment writing in `export_to_csv`.
- Verified XML export already uses `escape()`.
