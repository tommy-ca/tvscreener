---
status: completed
priority: p1
issue_id: "053"
tags: [architecture, orchestration, code-review]
dependencies: []
---

# Problem Statement
Critical business logic is trapped within `tvscreener/cli.py`. Functions for building configurations, metadata, and orchestrating scans are not reusable by other interfaces (like the MCP server or future web APIs). This leads to fragmentation and makes the system difficult to test in isolation.

# Findings
- **File**: `tvscreener/cli.py`
- **Trapped Logic**: `_build_opportunity_config`, `_build_opportunity_metadata`, `_filter_by_confluence`, and the main `run_*_scan` orchestrators.
- **Impact**: The MCP server (in `mcp/tools.py`) currently has to re-implement or call into the CLI logic, creating tight coupling and duplication.

# Proposed Solutions
1. **New Orchestrator Module**: Extract all `run_*_scan` logic and config builders into `tvscreener/lib/orchestrator.py`.
2. **Controller Pattern**: Use a `ScreenerController` that accepts validated dataclasses and handles the full execution/export/logging lifecycle.

# Recommended Action
Implement Solution 1: Move orchestration and config building out of `cli.py` into a reusable library module.

# Acceptance Criteria
- [x] `cli.py` is reduced to argument parsing and delegating to the orchestrator.
- [x] MCP tools use the same orchestrator as the CLI.
- [x] Orchestration logic can be unit tested without `argparse.Namespace`.

# Work Log
### 2026-02-28 - Orchestration Refactor Complete
**By:** Antigravity (Expert Code Review Resolution Specialist)
- Extracted `run_opportunity_scan`, `run_strategy_scan`, and config builders into `tvscreener/lib/orchestrator.py`.
- Introduced `ScanRequest` and `ScreenerController` for unified orchestration.
- Refactored `cli.py` to delegate to the orchestrator.
- Updated `mcp/tools.py` to use the same orchestrator logic, removing duplication.
