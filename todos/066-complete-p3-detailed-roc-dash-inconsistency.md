---
status: complete
priority: p3
issue_id: "066"
tags: [display, emoji, consistency, cleanup]
dependencies: []
---

# Detailed view ROC shows text dash instead of emoji

## Problem Statement

In the detailed view (`--detailed`), when a ROC value is exactly 0, the row shows a plain text `-` dash:

```
│ 240  │ +0.11 🟢 │ +0.40 🟢 │ -0.18 🔴 │ -         │
```

All other cells use emojis. The `-` is visually inconsistent with the emoji system.

## Findings

- `forex_opportunity.py:389` — conditional: `f"{roc_val:+.2f} {roc_sign}" if roc_val != 0 else "-"`
- The `roc_val != 0` check was originally for hiding irrelevant ROC data
- Now that all other indicators are emojis, the text dash breaks the visual pattern

## Proposed Solutions

### Option 1: Show emoji for zero ROC

**Approach:** Change `"-"` to `"+0.00 ⚪"` — same format as all other cells.

**Effort:** 1 minute (single line change)

**Risk:** Low

## Recommended Action

Change line 389 from `else "-"` to `else "+0.00 ⚪"`.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_opportunity.py:389`

## Acceptance Criteria

- [ ] Zero ROC values show `+0.00 ⚪` instead of `-`
- [ ] Non-zero ROC values still show `{val:+.2f} {emoji}`

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Spotted during audit of `--detailed` output for USDJPY (240 TF ROC = -0.00)
