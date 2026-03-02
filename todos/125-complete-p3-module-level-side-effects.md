---
status: complete
priority: p3
issue_id: "125"
tags: [quality, patterns, code-review]
dependencies: []
---

# Module-Level Side Effects for Renderer Registration

## Problem Statement

Renderer registrations at the bottom of `forex_strategy.py` (line 616) and `forex_opportunity.py` (line 232) use `# noqa: E402` imports to register at module import time. This creates fragile import-order dependencies.

## Findings

- `tvscreener/lib/screeners/forex_strategy.py:616-622` — Import + register at module level
- `tvscreener/lib/screeners/forex_opportunity.py:232-239` — Same pattern
- Both suppress E402 lint warning

## Proposed Solutions

### Option 1: Move to __init__.py or Explicit Init

**Approach:** Register in a `register_renderers()` function called from app entry point.

**Effort:** 30 minutes
**Risk:** Low

## Recommended Action

**Move to explicit init.** Create `register_renderers()` function called from app entry point instead of module-level imports.

## Acceptance Criteria

- [ ] No `# noqa: E402` suppressions needed
- [ ] Renderer registration is explicit, not import-time side effect

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code (pattern-recognition-specialist, python-reviewer)
