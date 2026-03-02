---
status: completed
priority: p3
issue_id: "074"
tags: [display, consistency, cli]
dependencies: []
---

# Standardize truncation limits across views

## Problem Statement

Different views use different default row limits: opportunity summary head(20), detailed head(10), matrix head(15), strategy summary configurable limit(20). This is inconsistent and undocumented.

## Findings

- `forex_opportunity.py` summary: `df.head(20)` hardcoded
- `forex_opportunity.py` detailed: `df.head(10)` hardcoded
- `forex_opportunity.py` matrix: `df.head(15)` hardcoded
- `forex_strategy.py` summary: `limit` parameter (default 20)
- No `--limit` CLI argument to override

## Proposed Solutions

### Option 1: Standardize defaults + add --limit CLI arg (Recommended)

**Approach:** Define view-specific defaults as constants. Add `--limit` CLI arg that overrides all defaults. Pass through to both scanners.

**Effort:** 30 minutes | **Risk:** Low

## Acceptance Criteria

- [x] View defaults documented as constants
- [x] `--limit N` CLI arg overrides default for any view
- [x] Both scanners respect the limit
- [x] All existing tests pass
