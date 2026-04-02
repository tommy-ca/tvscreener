# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Change: Configurable Iceberg lakehouse catalog (local or remote)

## Why
The Iceberg catalog and warehouse are currently effectively “fixed” to a local SQLite catalog +
local file warehouse. This blocks multi-process and multi-machine workflows, prevents durable
execution environments from sharing a single catalog, and forces operators to fork code for
environment-specific lakehouse setups.

## What Changes
- Add a nested `lakehouse` configuration group to the existing layered Pydantic settings system
  (YAML → ENV/.env → defaults).
- Support both:
  - **local** mode: SQLite SQL catalog + file warehouse under `~/.tvscreener/lakehouse`
  - **remote** mode: SQL catalog URI (e.g. Postgres) + shared warehouse URI (e.g. S3)
- Refactor `LakehouseManager` to read catalog/warehouse settings from `ScreenerSettings` instead of
  hard-coded paths.
- Ensure the CLI `--config` YAML path influences lakehouse initialization for the process.
- Document the configuration in the multi-asset design plan and default `tvscreener.yaml`.

## Impact
- Affected specs: `lakehouse-catalog-config`
- Affected code:
  - `tvscreener/config/settings.py`
  - `tvscreener/config/loader.py`
  - `tvscreener/lib/lakehouse/manager.py`
  - `tvscreener/lib/lakehouse/__init__.py`
  - `tvscreener/lib/orchestrator.py`
  - `tvscreener.yaml`
- Affected docs:
  - `docs/plans/2026-03-03-multi-asset-iceberg-catalog-and-table-design-plan.md`

