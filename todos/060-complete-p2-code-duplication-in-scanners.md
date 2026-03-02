---
status: complete
priority: p2
issue_id: "060"
tags: [architecture, dry, code-review]
dependencies: []
---

# Problem Statement
`ForexOpportunityScreener` and `ForexStrategyScanner` share nearly identical implementation logic for preparing enriched data, handling exports, and rendering summaries. This duplication violates DRY principles and makes it harder to add new features (like Stock/Crypto support) consistently.

# Findings
- **Duplicated Methods**: `_prepare_enriched_data`, `export`, and parts of `print_summary`.
- **Duplicated Logic**: Renaming technical columns to human-readable ones.

# Proposed Solutions
1. **Base Scanner Class**: Extract shared UI and export logic into a `BaseScanner` abstract class.
2. **Export Mixin**: Use a Mixin to provide standard export/summary capabilities to any scanner.

# Recommended Action
Implement a `BaseScanner` or `ExportMixin` to centralize formatting and export orchestration.

# Acceptance Criteria
- [x] `export` and `_prepare_enriched_data` logic is defined in only one place.
- [x] Both scanners inherit or compose this shared functionality.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Pattern Recognition Specialist)
- Identified high degree of code duplication between scanner types.

### 2026-02-28 - Unified Scanners
**By:** Antigravity
- Implemented `ExportMixin` in `base.py` to centralize formatting and export orchestration.
- Refactored `ForexOpportunityScreener` and `ForexStrategyScanner` to use `ExportMixin`.
- Eliminated duplicated `export` and column renaming logic.
