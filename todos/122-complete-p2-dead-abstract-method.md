---
status: complete
priority: p2
issue_id: "122"
tags: [dead-code, simplicity, code-review]
dependencies: []
---

# _get_strength_sign Abstract Method Never Called

## Problem Statement

`_get_strength_sign()` is defined as `@abstractmethod` in `BaseOpportunityScreener` (base.py:344), forcing implementations in `ForexOpportunityScreener` and `GenericOpportunityScreener`. However, grep confirms **zero call sites** exist. All rendering uses `VisualStyler` methods instead.

## Findings

- `tvscreener/lib/screeners/base.py:343-346` — Abstract definition
- `tvscreener/lib/screeners/factory.py:47-57` — Implementation (11 lines)
- `tvscreener/lib/screeners/forex_opportunity.py:214-229` — Implementation (16 lines)
- Zero callers found in entire codebase

## Proposed Solutions

### Option 1: Delete All Three

**Approach:** Remove abstract definition and both implementations. ~28 lines removed.

**Effort:** 5 minutes
**Risk:** None

## Recommended Action

**Delete all three.** Remove abstract definition from `BaseOpportunityScreener` and implementations from both subclasses. ~28 lines removed.

## Acceptance Criteria

- [ ] Abstract method removed from BaseOpportunityScreener
- [ ] Implementations removed from subclasses
- [ ] All tests pass

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (code-simplicity-reviewer)
