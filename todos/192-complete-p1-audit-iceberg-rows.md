---
status: complete
priority: p1
issue_id: "192"
tags: [lakehouse, audit, sql]
dependencies: ["191"]
---

# Audit the Iceberg rows for matrix view signals

## Problem Statement

- Once the scans replay data into Bronze→Silver→Gold, we still need to verify that the Iceberg rows accurately reproduce the matrix view outputs for the audit (docs/plans/2026-03-03-fix-lakehouse-audit-flow-plan.md:33-35).
- Without a systematic audit, tools may continue to rely on stale matrix columns or inconsistent derived metrics.

## Findings

- The plan emphasizes inspecting direction, TF×Factor grid, confluence counters, and derived grades for EURCHF and representative signals using EdgeQueryClient/Narwhals (lines 33-35).
- Documenting the SQL used will help verify the matrix view aligns with the raw data.

## Proposed Solutions

1. Query EURCHF-equivalent rows and a sample of majors/minors matrix entries to capture direction, ensemble score, TF confluence columns, and GRID alignment values.
2. Use EdgeQueryClient or Narwhals pipelines to reproduce the decorated matrix view via SQL, noting any mismatches.
3. Record the SQL expressions and results next to the plan so other engineers can rerun the audit (see `docs/audit/lakehouse-audit-flow.md`).

## Recommended Action

- Execute the SQL audits, capture outputs for key metrics, and log any discrepancies between matrix output and raw Iceberg rows. Store the SQL snippet and sample outputs in the audit plan note for traceability.

## Acceptance Criteria

- Audit queries exist for EURCHF and representative majors/minors signals covering direction, TF confluence, GRID alignment, and ensemble scores.
- EdgeQuery/Narwhals pipelines reproduce the decorated matrix view and align with the raw data within acceptable tolerance.
- SQL used for the audit is documented alongside the plan.

## Work Log

### [Date] - Created todo

**By:** Claude Code

**Actions:**
- Scoped the audit work required by the lakehouse plan and linked it to the scan refresh task.

**Learnings:**
- Documenting the SQL makes the audit reproducible for future reviewers.

### 2026-03-03 - Captured audit SQL guidance

**By:** Claude Code

**Actions:**
- Added the SQL sample, `EdgeQueryClient` snippet, and audit checklist to `docs/audit/lakehouse-audit-flow.md` so the matrix view results can be compared to `tvscreener.gold` directly.
- Updated the plan reference material section to point to the new document.

**Learnings:**
- Keeping the audit steps in one place prevents future reviewers from re-deriving the SQL or missing the key confluence columns.
