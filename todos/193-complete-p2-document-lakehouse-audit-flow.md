---
status: complete
priority: p2
issue_id: "193"
tags: [documentation, lakehouse, audit]
dependencies: ["192"]
---

# Document the lakehouse audit flow

## Problem Statement

- The audit plan lacks executable steps for future reviewers to reproduce the lakehouse-first review, and downstream docs still point to `exports/` as a signal source (docs/plans/2026-03-03-fix-lakehouse-audit-flow-plan.md:27-40).

## Findings

- The plan calls out documenting inspection steps/results, SQL used, and the new lakehouse-first flow so other engineers know to trust Iceberg data (lines 27-42).
- Without updated docs, future auditors may still run scans against `exports/` or misinterpret matrix outputs.

## Proposed Solutions

1. Expand the plan or companion note with the audit queries and observed outputs for EURCHF and representative majors/minors signals.
2. Update README/docs to describe `tvscreener.gold` as canonical and to link to this audit plan.
3. Record which tools/pipelines (EdgeQueryClient, Narwhals, PyIceberg) reproduce the matrix view so the process is actionable.

## Recommended Action

- Capture the documented steps, SQL queries, and verification notes in the plan/docs, and ensure the README states the lakehouse-first expectation.

## Acceptance Criteria

- The `Lakehouse Audit Flow` plan or companion note contains documented SQL steps and outputs for key signals.
- README/docs emphasize the lakehouse-first audit flow and mention `tvscreener.gold` as the canonical signal table.
- Future auditors can replay the documented queries without relying on `exports/` outputs.

## Work Log

### [Date] - Created todo

**By:** Claude Code

**Actions:**
- Bubbled up the documentation effort that follows the audits.

**Learnings:**
- Clear docs keep the lakehouse-first expectations alive for future reviewers.

### 2026-03-03 - Published audit reference doc

**By:** Claude Code

**Actions:**
- Authored `docs/audit/lakehouse-audit-flow.md` with the full sequence of export cleanup, matrix scanner commands, and SQL audit checks.
- Added the README `Lakehouse Audit Flow` section and the plan reference material section so the documentation is discoverable.

**Learnings:**
- A single companion guide makes the lakehouse-first audit repeatable for any reviewer without needing to chase down dispersed notes.
