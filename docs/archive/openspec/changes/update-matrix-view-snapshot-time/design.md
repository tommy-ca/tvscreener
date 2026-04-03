# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Matrix view snapshot label

### Source of truth
For analytics reruns, the matrix view renders from `tvscreener.signals_latest` which includes `fetched_at_utc`.

### Snapshot label derivation
- If `fetched_at_utc` is present and parseable:
  - compute `min(fetched_at_utc)` and `max(fetched_at_utc)`
  - render:
    - `Snapshot: <ts> UTC` when min == max
    - `Snapshot: <min>..<max> UTC` when min != max
- If `fetched_at_utc` is missing or empty:
  - do not display a snapshot label

### Rendering
The snapshot label is passed as `snapshot_label=...` through `ExportMixin.print_summary(...)` into the Rich console
renderer. Matrix titles are updated:
- Opportunity: `Confluence Matrix (Snapshot: ...)`
- Strategy: `Strategy Matrix: <strategy> (Snapshot: ...)`

