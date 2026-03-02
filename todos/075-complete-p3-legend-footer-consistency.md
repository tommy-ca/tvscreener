---
status: complete
priority: p3
issue_id: "075"
tags: [display, consistency, polish]
dependencies: []
---

# Add legend/footer consistency across views

## Problem Statement

The matrix view shows a legend (`🟢=Bullish 🔴=Bearish ⚪=Neutral`) and a count footer, but these are inconsistent across views and scanners. The summary view shows a different footer format. The strategy scanner's footer says "Total signals: N" while opportunity says "Showing top 20 of N opportunities".

## Findings

- Opportunity matrix: legend + "Showing top 15 of N opportunities"
- Opportunity summary: "Showing top 20 of N opportunities"
- Strategy summary: "Total signals: N"
- No legend in summary or detailed views (emojis used without explanation)

## Proposed Solutions

### Option 1: Standardize footer format (Recommended)

**Approach:** Use consistent footer format: `"Showing {shown} of {total} {label}"` across all views and scanners. Add legend to detailed view (since it uses emojis).

**Effort:** 30 minutes | **Risk:** Low

## Acceptance Criteria

- [x] Footer format consistent: `"Showing {shown} of {total} {label}"`
- [x] Legend shown in matrix and detailed views for both scanners
- [x] All existing tests pass
