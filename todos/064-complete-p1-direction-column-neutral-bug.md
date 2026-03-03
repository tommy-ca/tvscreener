---
status: complete
priority: p1
issue_id: "064"
tags: [display, emoji, ux, bug]
dependencies: []
---

# Direction column shows ⚪ for weak signals — hides long/short

## Problem Statement

After the emoji migration, pairs with weak ensemble scores (e.g., GBPNZD at -0.02, AUDNZD at -0.04) show ⚪ in the Direction column. Users cannot tell if the signal is long or short. This is a regression from the previous `SHORT =` / `LONG =` text display which was unambiguous.

The ⚪ emoji should be reserved for cell-level factor values (TREND/MA/OSC/ROC columns) where "neutral" is semantically correct. In the Direction column, the user always needs to know the side.

## Findings

- `_get_strength_sign()` in `forex_opportunity.py:462-477` is used for **two different purposes**:
  1. Cell-level factor values (detailed view, matrix view) — ⚪ is correct here
  2. Direction column in summary table (line 324) and title in detailed view (line 359) — ⚪ loses direction info
- The threshold for ⚪ is `|value| < 0.1` — many pairs fall in this range
- In the minors scan, 6 of 16 pairs showed ⚪ (37% of results have ambiguous direction)
- Strategy scanner `forex_strategy.py:634-643` has the same issue but less impactful since strategy signals are pre-filtered for direction

## Proposed Solutions

### Option 1: Never show ⚪ in Direction column — split the method usage

**Approach:** In the summary table and detailed title, use `ensemble > 0 → 🟢 / ensemble <= 0 → 🔴` (always show direction). Keep `_get_strength_sign()` as-is for cell-level values. Add the strength level via the *count* of emojis:
- `ensemble >= 0.5` → `🟢🟢` (strong long)
- `ensemble >= 0.1` → `🟢` (normal long)
- `0 < ensemble < 0.1` → `🟢` (weak long — same emoji as normal, differentiated by Ensemble column)
- `-0.1 < ensemble <= 0` → `🔴` (weak short)
- `ensemble <= -0.1` → `🔴` (normal short)
- `ensemble <= -0.5` → `🔴🔴` (strong short)

**Pros:**
- Direction is always visible
- Simple change — just adjust the caller, not the method
- Ensemble column already shows the precise strength

**Cons:**
- Weak and normal look the same (both single emoji)

**Effort:** 15 minutes

**Risk:** Low

---

### Option 2: Compound emoji for weak signals (🟢⚪ / 🔴⚪)

**Approach:** Add a new return value for weak signals: direction circle + white circle.

**Pros:**
- Shows both direction and weakness
- Three distinct strength levels per direction

**Cons:**
- 🟢⚪ is a novel notation — not self-explanatory
- Adds width to the column
- More complex to implement and explain

**Effort:** 30 minutes

**Risk:** Medium (user confusion)

## Recommended Action

**Option 1** — Never show ⚪ in Direction column. In `print_summary._render()` and `_render_detailed()`, replace `self._get_strength_sign(ensemble)` with a direction-specific helper that always returns 🟢 or 🔴 (with doubles for strong). The `_get_strength_sign()` method stays unchanged for cell-level use.

## Technical Details

**Affected files:**
- `tvscreener/lib/screeners/forex_opportunity.py:324` — summary `direction_sign`
- `tvscreener/lib/screeners/forex_opportunity.py:359` — detailed title `direction_sign`
- `tvscreener/lib/screeners/forex_strategy.py:672-673` — strategy direction display

**Approach:** Add a small helper or inline logic:
```python
def _direction_emoji(self, value: float) -> str:
    if value >= 0.5: return "🟢🟢"
    if value > 0: return "🟢"
    if value <= -0.5: return "🔴🔴"
    return "🔴"
```

## Acceptance Criteria

- [ ] Summary table Direction column never shows ⚪
- [ ] Detailed view title never shows ⚪
- [ ] Strategy scanner Direction column never shows ⚪
- [ ] Cell-level factor columns still show ⚪ for neutral values
- [ ] All 209 unit tests pass
- [ ] Visual verification: minors scan shows 🟢/🔴 for all 16 pairs

## Work Log

### 2026-03-01 - Initial Discovery

**By:** Claude Code

**Actions:**
- Identified during audit of emoji migration output
- 6/16 minors pairs show ⚪ in Direction column (GBPAUD, EURAUD, AUDCAD, GBPCAD, GBPNZD, AUDNZD)
- Root cause: `_get_strength_sign()` treats |ensemble| < 0.1 as neutral

**Learnings:**
- The method serves two semantically different purposes (direction indicator vs cell strength indicator)
- Splitting these concerns is the clean fix
