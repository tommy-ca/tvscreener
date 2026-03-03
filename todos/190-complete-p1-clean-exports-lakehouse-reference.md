---
status: complete
priority: p1
issue_id: "190"
tags: [lakehouse, exports, audit]
dependencies: []
---

# Clean and seal the exports reference

## Problem Statement

- `exports/` still holds stale parquet/text snapshots that can diverge from the Iceberg-backed `tvscreener.gold` table, which is now the canonical source for audits (docs/plans/2026-03-03-fix-lakehouse-audit-flow-plan.md:15-28).
- Scanners continue to write into `exports/` before refreshing lakehouse tables, wasting space and confusing downstream reviews about the proper source of truth.

## Findings

- The plan explicitly wants `exports/` to become read-only or be removed so that only lakehouse data drives audits (lines 25-33).
- Documentation/tooling still reference writing to `exports/`, so operators may not realize `tvscreener.gold` is preferred.

## Proposed Solutions

1. Prevent routine scans from writing to `exports/` unless `--write-exports` is explicitly requested.
2. Delete or archive the existing contents so the folder only contains reference snapshots.
3. Update README/docs to state `exports/` is reference-only and to emphasize `tvscreener.gold` as the authoritative lakehouse table.

## Recommended Action

- Lock down export writes, clean up the directory contents, and publish updated docs/plan text promoting the Iceberg lakehouse as the audit source.

## Acceptance Criteria

- Default scanner runs no longer write to `exports/`.
- Documentation labels `exports/` as reference-only and cites `tvscreener.gold` as canonical (lines 31-40).
- `--write-exports` remains the sole flag allowing updates to the folder.

## Work Log

### [Date] - Created todo

**By:** Claude Code

**Actions:**
- Captured the audit flow plan and defined the exports cleanup scope.

**Learnings:**
- Removing exports writes is a prerequisite for a lakehouse-first audit flow.

### 2026-03-03 - Documented exports reference policy

**By:** Claude Code

**Actions:**
- Added the README ``Lakehouse Audit Flow`` section to highlight `tvscreener.gold` as the canonical table and to point back to this plan.
- Authored `docs/audit/lakehouse-audit-flow.md` with cleanup guidance, the `--write-exports` opt-in policy, and links back to the plan.
- Updated the plan so this todo is referenced in the new reference material section.

**Learnings:**
- Surface-level documentation keeps auditors from mistaking `exports/` for the source of truth before rerunning scans.
