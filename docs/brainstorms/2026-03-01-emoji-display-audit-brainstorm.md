---
date: 2026-03-01
topic: emoji-display-audit
---

# Emoji Display System Audit

## What We're Building

Polish pass on the emoji-based direction/strength indicator system introduced in the scanner display layer. The emoji migration (from `++/+/=/−/−−` text to `🟢🟢/🟢/⚪/🔴/🔴🔴`) works but exposed several visual and semantic issues that need fixing.

## Why This Matters

The scanner output is the primary user interface. Direction ambiguity (Issue #1) means users can't distinguish long from short on weak signals — the most important signals to get right since they're closest to inflection points.

## Key Decisions

- **Direction column never shows ⚪**: The `_get_strength_sign()` method is used for two different purposes — cell-level factor values (where ⚪ makes sense: "this factor is neutral") and the Direction column (where ⚪ hides information). The fix: the Direction column always shows at least 🟢/🔴 based on ensemble sign. ⚪ is reserved for cell-level use only.
- **Matrix uses single emojis only**: Double emojis (🟢🟢) cause Rich column truncation. The matrix view prioritizes density — showing all 12 cells at a glance. Losing the strong/normal distinction is acceptable since the matrix already shows the raw alignment pattern visually.
- **Detailed view ROC dash → emoji**: The `-` text dash for zero ROC is inconsistent; use `⚪` for uniformity.

## Issues Identified

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | Direction lost for neutral signals (⚪ hides long/short) | Critical | Always show 🟢/🔴 in Direction column |
| 2 | Detailed view ROC row shows `-` text dash | Minor | Change to `⚪` |
| 3 | Matrix column truncation from double emojis | Moderate | Single emoji only in matrix |
| 4 | Direction import cleanup in _render() | Cleanup | Remove unused variable |
| 5 | Strategy scanner Direction column has `style="green"` | Minor | Remove style override |

## Open Questions

None — all design decisions resolved.

## Next Steps

→ File-todos created for each issue, ready to implement.
