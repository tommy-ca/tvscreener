---
status: ready
priority: p2
issue_id: "065"
tags: [display, emoji, matrix, ux]
dependencies: []
---

# Matrix view column truncation with double emojis

## Problem Statement

The matrix view uses pipe-joined double emojis per cell (e.g., `🟢🟢|🟢🟢|🟢`). Rich auto-truncates these with `…` when the terminal is not wide enough, making the matrix unreadable for columns with many strong signals (especially MA and ROC).

## Findings

- Double emojis (`🟢🟢`) take ~2 character widths each in most terminals
- With 3 TFs pipe-joined: `🟢🟢|🟢🟢|🟢` = 5 emojis + 2 pipes = ~12 visual chars
- Rich Table truncates columns that exceed available width
- The MA column is most affected since MA values tend to be extreme (±0.8-0.93)
- Observed truncation: `🟢🟢|🟢🟢…` (loses 3rd TF entirely)

## Proposed Solutions

### Option 1: Single emoji only in matrix

**Approach:** Matrix cells show only 🟢/⚪/🔴 (no doubles). The matrix prioritizes density — showing all 12 grid cells at a glance. Strong/normal distinction is sacrificed for readability.

Mapping: `value > 0 → 🟢`, `value < 0 → 🔴`, neutral → `⚪`

**Pros:**
- No truncation — `🟢|🟢|🟢` always fits
- Matrix becomes a pure alignment heatmap (green/white/red)
- Grid column already shows the aggregate count
- Detailed view still shows full strength with doubles

**Cons:**
- Loses strong/normal distinction in matrix view

**Effort:** 15 minutes

**Risk:** Low

## Recommended Action

**Option 1** — Single emoji in matrix. Add an `is_matrix=True` kwarg to `_get_strength_sign()`, or create a separate `_matrix_sign()` helper that only returns 🟢/⚪/🔴. Use it in `_render_matrix()` cell generation.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_opportunity.py:435-440` — matrix cell generation
- `tvscreener/lib/screeners/forex_opportunity.py:459` — legend text update

## Acceptance Criteria

- [ ] Matrix cells show only single emojis (🟢/⚪/🔴)
- [ ] No column truncation in matrix view at standard terminal widths (80+ cols)
- [ ] Legend updated: `🟢=Bullish  🔴=Bearish  ⚪=Neutral`
- [ ] Detailed view still shows double emojis for strength
- [ ] Visual verification with `--matrix` flag

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Observed truncation in `--matrix` output for MA and ROC columns
- Confirmed Rich auto-truncation behavior with `…` suffix
- Tested string widths: single emoji pipes `🟢|🟢|🟢` = 5 chars vs double `🟢🟢|🟢🟢|🟢` = 7+ chars
