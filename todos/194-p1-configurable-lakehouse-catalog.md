---
status: in_progress
priority: p1
issue_id: "194"
tags: [lakehouse, iceberg, config]
dependencies: []
---

# Configurable Iceberg lakehouse catalog (local or remote)

## Problem Statement

- Iceberg catalog/warehouse settings were historically embedded in `tvscreener/lib/lakehouse/manager.py`,
  making it hard to run durable workflows or share a catalog across processes/machines.
- We need a layered configuration approach (YAML + ENV) with **nested config groups** so lakehouse
  configuration is consistent with other scanner settings.

## Proposed Solution

- Add a grouped nested settings block:
  - `ScreenerSettings.lakehouse.catalog.mode = local|remote`
  - local: SQLite SQL catalog + file warehouse under `~/.tvscreener/lakehouse`
  - remote: SQL catalog URI (e.g. Postgres) + shared warehouse URI (e.g. S3)
- Initialize the lakehouse singleton early from the CLI `--config` path so the configured catalog is
  used for the entire process.
- Document configuration examples in `tvscreener.yaml` and the multi-asset plan docs.

## Files / touchpoints

- `tvscreener/config/settings.py`
- `tvscreener/config/loader.py`
- `tvscreener/lib/lakehouse/manager.py`
- `tvscreener/lib/lakehouse/__init__.py`
- `tvscreener/lib/orchestrator.py`
- `tvscreener.yaml`
- `docs/architecture/LAKEHOUSE.md`
- `docs/plans/2026-03-03-multi-asset-iceberg-catalog-and-table-design-plan.md`

## Acceptance Criteria

- CLI and library can load a local Iceberg catalog by default without code changes.
- Setting `lakehouse.catalog.mode=remote` requires `uri` and `warehouse` and is validated.
- `--config` influences lakehouse initialization for the current CLI process.
- Documentation shows the exact YAML/ENV keys needed to configure local vs remote catalogs.

