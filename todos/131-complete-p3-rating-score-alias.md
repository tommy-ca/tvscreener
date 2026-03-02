---
status: complete
priority: p3
issue_id: "131"
tags: [quality, naming, code-review]
dependencies: []
---

# RATING_SCORE Alias Column Duplicates ENSEMBLE_SCORE

## Problem Statement

`score.py:302` creates `RATING_SCORE` as a copy of `ENSEMBLE_SCORE`. This creates two columns with identical data. No code references `RATING_SCORE` — it's a confusing alias.

## Findings

- `tvscreener/score.py:302` — `df["RATING_SCORE"] = df.get("ENSEMBLE_SCORE", 0.0)`
- `tvscreener/score.py:303` — `df["ROC_AVG"] = df.get("ROC_SCORE", 0.0)` (same pattern)
- Zero references to `RATING_SCORE` or `ROC_AVG` elsewhere in codebase

## Proposed Solutions

### Option 1: Delete Both Alias Lines

**Approach:** Remove lines 302-303 from score.py.

**Effort:** 2 minutes
**Risk:** None (no consumers)

## Recommended Action

**Delete both alias lines.** Remove lines 302-303 from `score.py`. Zero consumers exist.

## Acceptance Criteria

- [ ] No alias columns in scoring output
- [ ] All tests pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (pattern-recognition-specialist)
