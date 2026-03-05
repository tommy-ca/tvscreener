# Change: Update lakehouse audit flow (Iceberg-first, optional snapshots)

## Why
The project has moved to an Iceberg-backed medallion pipeline, but the audit documentation and
operator habits still treat repository-level snapshots (historically `exports/`) as a primary data
source. This creates drift, confusion about the canonical source of truth, and non-reproducible
reviews when on-disk artifacts are stale or missing.

## What Changes
- Update audit documentation to be **lakehouse-first**: audits run against `tvscreener.bronze`,
  `tvscreener.silver`, and `tvscreener.gold` by default.
- Remove the repository-level `exports/` directory as a *default* concept. On-disk snapshots remain
  possible, but only as an explicit, intentional operator action.
- Define a reproducible audit record template (run metadata + Iceberg snapshot IDs + SQL) so audits
  can be replayed and compared over time.
- Align multi-asset design documentation with the current implementation status (run envelope,
  identity columns, overwrite scoping, coverage gating).

## Impact
- Affected specs: `lakehouse-audit-flow`
- Affected docs:
  - `docs/audit/lakehouse-audit-flow.md`
  - `docs/plans/2026-03-03-fix-lakehouse-audit-flow-plan.md`
  - `docs/plans/2026-03-03-rerun-forex-scanners-validate-duckdb-plan.md`
  - `docs/plans/2026-03-03-multi-asset-iceberg-catalog-and-table-design-plan.md`
  - `README.md`
- Affected code (follow-up tasks, if we want the docs to be enforced by tooling):
  - `tvscreener/lib/query.py` (remove any default cache path under repository snapshots)
  - `tvscreener/cli.py`, `tvscreener/lib/orchestrator.py` (explicit opt-in gating if we keep a
    dedicated snapshots directory name)

## Assumptions
- Iceberg tables are available and queryable locally via the configured catalog/warehouse defaults.
- Operators may still want *optional* on-disk snapshots for ad-hoc debugging, but audits must not
  depend on those artifacts for correctness.

