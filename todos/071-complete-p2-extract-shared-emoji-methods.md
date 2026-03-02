---
status: completed
priority: p2
issue_id: "071"
tags: [refactor, display, emoji, base-class]
dependencies: []
---

# Extract shared emoji methods to base class (Completed)

## Problem Statement

Both `ForexOpportunityScreener` and `ForexStrategyScanner` implement their own `_get_strength_sign()` with different semantics. The opportunity scanner also has `_direction_emoji()` and `_matrix_sign()` that the strategy scanner lacks but will need (for todos 068/069). This duplicated rendering logic should be extracted into a shared location.

## Findings

- `ForexOpportunityScreener._get_strength_sign(value, is_roc=False)` — threshold-based, returns emojis based on value magnitude
- `ForexOpportunityScreener._direction_emoji(value)` — never returns ⚪, always 🟢 or 🔴
- `ForexOpportunityScreener._matrix_sign(value)` — single emoji only (🟢/🔴/⚪)
- `ForexStrategyScanner._get_strength_sign(score, direction=...)` — integer score-based (1-3), direction-aware
- `BaseOpportunityScreener._get_strength_sign()` — abstract, defined but only used by opportunity

## Proposed Solutions

### Option 1: Move common emoji methods to ExportMixin (Recommended)

**Approach:** Move `_direction_emoji()` and `_matrix_sign()` to `ExportMixin` (shared by both scanners). Keep `_get_strength_sign()` as an override in each scanner since the semantics genuinely differ.

**Pros:**
- Both scanners inherit `_direction_emoji()` and `_matrix_sign()` automatically
- `_get_strength_sign()` remains overridable for scanner-specific logic
- Minimal class hierarchy changes

**Cons:**
- ExportMixin grows slightly

**Effort:** 1 hour

**Risk:** Low

## Acceptance Criteria

- [x] `_direction_emoji()` and `_matrix_sign()` defined in `ExportMixin` or `BaseOpportunityScreener`
- [x] Both scanners use inherited methods (no duplication)
- [x] `_get_strength_sign()` remains scanner-specific (opportunity: threshold, strategy: score)
- [x] All existing tests pass
- [x] Opportunity scanner output unchanged

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Audited emoji method definitions across both scanners
- Identified `_direction_emoji()` and `_matrix_sign()` as safely extractable
- Identified `_get_strength_sign()` as intentionally different (must stay overridden)

### 2026-03-01 - Implementation

**By:** Antigravity

**Actions:**
- Moved `_direction_emoji` and `_matrix_sign` to `ExportMixin` in `base.py`.
- Removed duplicated methods from `ForexOpportunityScreener`.
- Refactored `ForexStrategyScanner._get_strength_sign` to use inherited `_direction_emoji`.
- Verified output remains identical for both scanners.
