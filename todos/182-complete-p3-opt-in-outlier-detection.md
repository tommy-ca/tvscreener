---
status: complete
priority: p3
issue_id: "182"
tags: [cleansing, silver, outlier-detection]
dependencies: ["143"]
---

# Implement Opt-in Volume Outlier Detection (Silver Layer)

## Problem Statement
Abnormal volume spikes in the TradingView API can sometimes represent flash crashes or data errors. While outlier detection helps filter noise, it can also hide valid market events.

## Findings
- Previous brainstorm proposed Z-Score volume outlier detection.
- Requirement: Disable by default to ensure data transparency.

## Proposed Solutions
1. **Z-Score Filter**: Implement a Narwhals-based Z-Score filter on the `relative_volume_10d_calc` column.
2. **Opt-in Logic**: Add a `--filter-outliers` CLI flag. Unless this flag is provided, the Silver layer standardization should NOT filter based on Z-Scores.

## Recommended Action
Implement the Z-Score logic as an optional transform in the Silver medallion stage.

## Acceptance Criteria
- [ ] Z-Score volume filtering is implemented using Narwhals.
- [ ] Outlier detection is **disabled by default**.
- [ ] Providing `--filter-outliers` correctly removes rows with `Z > 3`.

## Work Log
### 2026-03-02 - Task Created
- Transitioning to opt-in outlier detection per latest audit.
