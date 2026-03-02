---
status: complete
priority: p2
issue_id: "073"
tags: [strategy, display, normalization]
dependencies: ["072"]
---

# Normalize summary table columns across scanners

## Problem Statement

The opportunity scanner summary shows Rank, Pair, Direction, Ensemble, Confluence, TF, Factor, Grade — a rich set of columns. The strategy scanner shows only Pair, Direction, Confluence (integer). The visual information density differs significantly.

## Findings

- Opportunity summary: 8 columns with consistent structure
- Strategy summary: 3-5 columns varying by strategy type
  - Non-confluence: Pair, Direction, Confluence
  - Confluence: Pair, Direction, Pattern, Score, MR
- No Rank column in strategy summary
- No Grade column in strategy summary
- Column structure changes per strategy group (jarring for users)

## Proposed Solutions

### Option 1: Add Rank and Grade to strategy summary (Recommended)

**Approach:** Add Rank and Grade columns to the strategy summary tables. Requires todo 072 (grid confluence) to be completed first for Grade data. Keep strategy-specific columns (Pattern, MR) for the confluence strategy.

**Pros:**
- More information at a glance
- Consistent with opportunity scanner
- Grade provides immediate quality signal

**Cons:**
- Slightly wider tables
- Depends on 072 for Grade

**Effort:** 1 hour

**Risk:** Low

## Acceptance Criteria
- [x] Strategy summary includes Rank column (per-strategy-group ranking)
- [x] Strategy summary includes Grade column
- [x] Column order is consistent: Rank, Pair, Direction, [Strategy-specific], Grid, Grade
- [x] All existing tests pass

## Work Log

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Added Rank column to strategy summary tables with per-group numbering.
- Added Grade column to strategy summary tables.
- Normalized column order across all strategy types.
- Verified consistency with opportunity scanner layout.
- Marked Todo 073 as complete.

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Compared column sets between opportunity and strategy summary views
- Identified Rank and Grade as the most impactful additions
