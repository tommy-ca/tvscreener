# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
change_id: update-matrix-view-snapshot-time
type: change
status: proposed
---

## Why
Operators rerun analytics pipelines from Iceberg (`tvscreener.signals_latest`) and rely on the matrix view for
decision-making. Today the matrix view does not surface *which snapshot* (i.e. upstream fetch time) the view is
rendered from, which makes screenshots/logs harder to audit and compare.

## What changes
- Matrix view titles will include a **snapshot timestamp** derived from the dataframe’s `fetched_at_utc` column:
  - if a single timestamp is present: `Snapshot: <ts> UTC`
  - if multiple timestamps are present: `Snapshot: <min>..<max> UTC`
- Applies to:
  - opportunity matrix view (`Confluence Matrix`)
  - strategy matrix view (`Strategy Matrix: <strategy>`)

## Non-goals
- Do not introduce a new Iceberg “snapshot id” mechanism here.
- Do not change data/analytics pipeline semantics.

## Impact
- Pure UX/audit improvement: the matrix view becomes self-describing for replayability.

