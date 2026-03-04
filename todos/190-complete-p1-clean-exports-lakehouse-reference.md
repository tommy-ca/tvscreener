---
status: complete
priority: p1
issue_id: "190"
tags: [lakehouse, snapshots, audit]
dependencies: []
---

# Remove repository snapshot defaults (lakehouse-first)

## Problem Statement

- Repository-local parquet/text snapshots can drift from the Iceberg-backed `tvscreener.gold` table,
  which is the canonical source for audits.
- Audits and default scans must be Iceberg-first; any on-disk snapshot must be explicitly requested
  as a debugging artifact.

## Findings

- The lakehouse audit flow requires reproducibility from Iceberg snapshots, not from ad-hoc files.
- Documentation/tooling historically referenced repo-local snapshots, which can mislead auditors.

## Proposed Solutions

1. Remove repository snapshot outputs from the default workflow (scans write to Iceberg only).
2. Treat any on-disk snapshot as explicitly requested via `--output ./snapshots/...` (or equivalent).
3. Update README/docs to emphasize `tvscreener.gold` as the authoritative lakehouse table and to
   include a reproducible audit record template (snapshot IDs + SQL).

## Recommended Action

- Lock down export writes, clean up the directory contents, and publish updated docs/plan text promoting the Iceberg lakehouse as the audit source.

## Acceptance Criteria

- Default scanner runs do not write any repository-local snapshot files.
- Documentation describes Iceberg tables as canonical and treats on-disk snapshots as optional artifacts.
- Audit notes can be reproduced from Iceberg `snapshot_id`s and recorded SQL alone.

## Work Log

### [Date] - Created todo

**By:** Claude Code

**Actions:**
- Captured the audit flow plan and defined the snapshot-removal scope.

**Learnings:**
- Removing repository snapshot defaults is a prerequisite for a lakehouse-first audit flow.

### 2026-03-03 - Documented lakehouse-first audit policy

**By:** Claude Code

**Actions:**
- Added the README ``Lakehouse Audit Flow`` section to highlight `tvscreener.gold` as the canonical table and to point back to this plan.
- Authored `docs/audit/lakehouse-audit-flow.md` with the scan rerun sequence, SQL audit checks, and links back to the plan.
- Updated the plan so this todo is referenced in the new reference material section.

**Learnings:**
- Surface-level documentation keeps auditors from mistaking repository-local snapshots for the source of truth before rerunning scans.
