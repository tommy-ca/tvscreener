---
status: complete
priority: p2
issue_id: "062"
tags: [forex, configuration, code-review]
dependencies: []
---

# Problem Statement
RSI thresholds for mean-reversion signals are hardcoded to 30/70. This prevents users from adjusting signal sensitivity (e.g., using 20/80 for more extreme setups) without modifying the source code.

# Findings
- **File**: `tvscreener/lib/screeners/filter_utils.py`
- **Line**: 61410-61412 (approx)
- **Evidence**:
  ```python
  long_mask = rsi_values < 30
  short_mask = rsi_values > 70
  ```

# Proposed Solutions
1. **Configurable Thresholds**: Add `rsi_lower_threshold` and `rsi_upper_threshold` to `StrategyConfig`.
2. **Defaults**: Use 30/70 as defaults but allow overrides from CLI/YAML.

# Recommended Action
Make RSI thresholds configurable through the standard configuration pipeline.

# Acceptance Criteria
- [x] Users can specify custom RSI thresholds via CLI (e.g., `--rsi-lower 20`).
- [x] Default remains 30/70.

# Work Log
### 2026-02-28 - Initial Finding
**By:** Claude Code (Kieran Python Reviewer)
- Identified hardcoded numeric thresholds in indicator logic.

### 2026-02-28 - Implemented
- Added `rsi_lower` and `rsi_upper` to `ScreenerSettings`, `StrategyConfig`, and `ScanRequest`.
- Updated `detect_mean_reversion_signals` to use configurable thresholds.
- Added `--rsi-lower` and `--rsi-upper` to CLI.
