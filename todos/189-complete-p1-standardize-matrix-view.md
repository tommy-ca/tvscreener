---
status: complete
priority: p1
issue_id: "189"
tags: [matrix-view, scanners, dataops]
dependencies: []
---

# Standardize Matrix-first Scanner View

## Problem Statement

Opportunity and strategy scanners now share a DuckDB view, but the UI still defaults to the detailed view and the documented outputs describe inconsistent column sets. We need to shift the UX/CLI default to the matrix view and guarantee both matrix and detailed presentations use the same confluence-rich schema so downstream consumers can rely on `TOTAL_CONFLUENCE`, `GRID_TOTAL`, `TF_CONFLUENCE_*`, and `ENSEMBLE_SCORE` no matter the view.

## Findings

- CLI currently requires `--matrix` to show the confluence matrix; the plan now wants matrix as the default with detailed as optional.
- Matrix view already displays the necessary multi-timeframe confluence columns for majors/minors opportunities and strategies (rows logged from recent runs).
- Detailed view populates additional fields (scores/timeframe breakdown) but doesn’t consistently expose the confluence metrics required for analytics.
- Documentation/plan needs to call out how Narwhals + EdgeQueryClient pipelines filter the shared view; the CLI help text and plan sections need updates.

## Proposed Solutions

### Option 1: Matrix Default with Standardized Schema

**Approach:** Update the CLI default to run `--matrix` by default (internally add if flag absent). Ensure detailed mode leverages the same underlying view and make the plan/docs explicit. Adjust matrix/detailed renderers to include the necessary confluence columns.

**Pros:** Matches new requirements; users get confluence-first output automatically; detailed mode can be used for compliance or inspection.
**Cons:** Slight CLI behavior change; needs coordination with documentation.
**Effort:** 2-3 hours
**Risk:** Low

---

### Option 2: CLI Flag Interpretation with Documentation

**Approach:** Keep CLI defaults but update docs/plan to state always prefer `--matrix` and script wrappers (or alias) to add the flag. Update view docs to highlight consistent columns, but leave CLI untouched for compatibility.

**Pros:** No behavior change for existing scripts.
**Cons:** Doesn’t satisfy directive to make matrix default; weaker user guidance.
**Effort:** 1-2 hours
**Risk:** Medium (user confusion remains)

---

### Option 3: Matrix-first Renderer with Explicit Flag for Detailed

**Approach:** Modify renderer layers such that the CLI always calls matrix renderer unless `--detailed` is passed; detailed renderer reuses matrix column set by pulling the same view and adding extra columns.

**Pros:** Clear separation; ensures confluence columns appear anywhere.
**Cons:** Slight renderer refactor; requires careful testing.
**Effort:** 3-4 hours
**Risk:** Medium

## Recommended Action

- Update `cli.py`/`ScreenerController.run_from_args` so the matrix view is implied when neither `--matrix` nor `--detailed` is provided, keeping matrix as the default presentation.
- Harmonize detailed rendering to pull from the same matrix-backed view, ensuring confluence columns are surfaced regardless of view.
- Adjust documentation/plan text to mention the matrix-first default and optional detailed view; run matrix scans to confirm confluence columns are populated.

## Technical Details

**Affected files:**
- `tvscreener/cli.py` (flag defaults, help text)
- `tvscreener/lib/screeners/base.py` (renderers if tied to view)
- `tvscreener/lib/query.py` (confirm shared view exposes columns)
- `docs/plans/2026-03-03-rerun-forex-scanners-validate-duckdb-plan.md` (update sections to mention matrix default)

**Related components:**
- EdgeQueryClient pipelines for filtering
- Matrix renderer output and legend text

## Resources

- CLI help output showing `--matrix` flag
- Recent matrix runs logged in plan (majors/minors opportunities and strategies)

## Acceptance Criteria

- [x] CLI defaults to matrix output unless `--detailed` is specified
- [x] Matrix and detailed renderers use the same standardized confluence-rich schema
- [x] Documentation/plan clearly state matrix default and optional detailed
- [x] Tests/QA cover matrix view outputs for all scanners

## Work Log

### [Date] - Created todo

**By:** Claude Code

**Actions:**
- Captured request to make matrix view default
- Documented plan updates and CLI expectations

**Learnings:**
- Matrix output already shows required confluence columns
- Need final decision on renderer flow before implementation changes

### 2026-03-03 - Harmonized confluence schema

**By:** Claude Code

**Actions:**
- Defaulted the CLI to matrix-first output while ensuring detailed mode still shares the standardized schema
- Surface `TOTAL_CONFLUENCE`, `GRID_TOTAL`, `TF_CONFLUENCE_*`, and `ENSEMBLE_SCORE` inside both matrix and detailed renderers

**Learnings:**
- Highlighting the core confluence metrics makes downstream EdgeQuery filters more predictable

## Notes

- Renderer approach finalized: keep matrix compact by default.
