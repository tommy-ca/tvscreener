---
status: ready
priority: p3
issue_id: "067"
tags: [display, cleanup, style]
dependencies: []
---

# Strategy scanner Direction column has stale `style="green"`

## Problem Statement

In `forex_strategy.py`, the strategy scanner's `print_summary` defines the Direction column with `style="green"`:

```python
table.add_column("Direction", style="green")
```

This was appropriate when the column showed `LONG ++` text, but now it shows emojis (`🟢🟢`, `🔴`, `⚪`). The green style:
1. Doesn't visually affect emojis (they carry their own color)
2. Is semantically wrong for 🔴 short signals displayed in a green-styled column

## Findings

- `forex_strategy.py:657` — `table.add_column("Direction", style="green")`
- The Rich style applies to the cell text color, but emoji rendering typically ignores it
- Minor visual issue — most terminals render emoji color natively regardless of Rich style

## Proposed Solutions

### Option 1: Remove style or set to "white"

**Approach:** Change `style="green"` to no style or `style="white"`.

**Effort:** 1 minute

**Risk:** Low

## Recommended Action

Change to `table.add_column("Direction", justify="center")` — drop the style entirely.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_strategy.py:657`

## Acceptance Criteria

- [ ] Direction column has no color style override
- [ ] Emojis render with their native colors

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Found during code audit of strategy scanner display layer
