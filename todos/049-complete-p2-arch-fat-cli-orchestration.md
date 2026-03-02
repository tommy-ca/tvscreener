---
status: complete
priority: p2
issue_id: "049"
tags: [architecture, cli, code-review]
dependencies: []
---

# Problem Statement
`cli.py` has grown into a "Fat CLI" that handles argument parsing, configuration building, progress bars, output routing, and execution orchestration. This leads to heavy code duplication between scanners and makes the logic difficult to test or reuse.

# Findings
- **File:** `tvscreener/cli.py`
- **Evidence:** Duplicated `if/elif` blocks for file extension routing in both `run_opportunity_scan` and `run_strategy_scan`. Coupling to `argparse.Namespace`.

# Proposed Solutions
1. **ScannerController**: Extract a controller/runner class that takes a simple config object and handles the execution lifecycle.
2. **Shared Export Handler**: Create a `_handle_export` helper to de-duplicate file routing.

# Recommended Action
Extract shared logic into helper functions to reduce duplication.

# Acceptance Criteria
- [x] Extension-based routing logic exists in only one place (`_export_results` in `orchestrator.py`).
- [x] `run_opportunity_scan` and `run_strategy_scan` are significantly slimmed down and moved to orchestrator.
- [x] `cli.py` is reduced to argument parsing and delegating to `ScreenerController.run_from_args`.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code
- Identified high coupling and duplication in CLI module.

### 2026-02-28 - Implemented
- Created `run_from_args` in `ScreenerController` to handle `argparse` namespace conversion.
- De-duplicated export logic into `_export_results` in `orchestrator.py`.
- Moved all execution logic from `cli.py` to `orchestrator.py`.
