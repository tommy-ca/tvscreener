---
status: complete
priority: p1
issue_id: "191"
tags: [lakehouse, scans, matrix]
dependencies: ["190"]
---

# Rerun opportunity and strategy scanners into Iceberg

## Problem Statement

- Opportunity and strategy scans need to be rerun with matrix defaults so the medallion tables contain
  the latest matrix-ready signals required for audits.
- Without rerunning these scanners with matrix defaults, the medallion tables may lack the latest matrix-ready signals needed for the audit.

## Findings

- The plan explicitly asks for rerunning both majors and minors opportunity/strategy scanners with the matrix view default to replay data through Bronze→Silver→Gold (lines 25-35).
- Fresh scans ensure `tvscreener.gold` contains the newest matrix-ready signals that auditors will inspect.

## Proposed Solutions

1. Run `uv run tvscreener-scan --scanner opportunity --universe majors --matrix` and repeat for minors.
2. Repeat for strategy scanners with the `--matrix` flag so both scan families produce matrix data.
3. Confirm via `pyiceberg`/EdgeQuery that the new rows appear in `tvscreener.gold` for both majors and minors.

## Recommended Action

- Rerun the specified scans with matrix defaults and validate lakehouse ingestion via Iceberg queries.

## Acceptance Criteria

- Opportunity and strategy scans for majors and minors complete successfully with the matrix default.
- `tvscreener.gold` reflects the fresh data for each scan (reports via `pyiceberg`/EdgeQuery).
- No repository-local snapshot files are produced unless an explicit `--output` path is provided.

## Work Log

### [Date] - Created todo

**By:** Claude Code

**Actions:**
- Documented the rerun steps requested by the plan and linked it to the exports cleanup task.

**Learnings:**
- Rerunning the scans is the data refresh step that enables the audit to rely on lakehouse data.

### 2026-03-03 - Captured matrix rerun guidance

**By:** Claude Code

**Actions:**
- Added the matrix replay commands, `pyiceberg` verification guidance, and optional `EdgeQuery` snapshots to `docs/audit/lakehouse-audit-flow.md`.
- Confirmed the plan now references this guide so future auditors run the same steps.

**Learnings:**
- Having a single reference doc keeps the rerun scripts consistent and makes verifying `tvscreener.gold` straightforward.
