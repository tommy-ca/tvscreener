# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Context
`tvscreener` uses a local Iceberg lakehouse to persist medallion outputs (Bronze/Silver/Gold).
Today, the Iceberg SQL catalog and warehouse are initialized inside `LakehouseManager` with local
SQLite + a local file warehouse under the user’s home directory.

For multi-asset scaling and durable workflows, we need to configure the lakehouse catalog/warehouse
without code edits, using the project’s existing layered configuration mechanism.

## Goals / Non-Goals

### Goals
- Provide a first-class `lakehouse` config group in `ScreenerSettings`.
- Support **local** and **remote** SQL catalogs.
- Ensure the CLI `--config` YAML path affects Iceberg catalog initialization for that process.
- Keep backward compatibility: if no lakehouse config is provided, behavior matches the existing
  local SQLite + file warehouse defaults.

### Non-Goals
- Adding additional catalog backends beyond `sql` (e.g. REST) in this change.
- Implementing workflow engines (DBOS, Airflow, etc.) or catalog migration tooling.

## Settings Structure

YAML shape:

```yaml
lakehouse:
  catalog:
    mode: local|remote
    name: local
    type: sql
    local:
      base_dir: null
      catalog_db: catalog.db
      warehouse_dir: warehouse
    remote:
      uri: "postgresql+psycopg://..."
      warehouse: "s3://bucket/warehouse"
    properties: {}
```

ENV shape (nested delimiter `_`):

```bash
TVSCREENER_LAKEHOUSE_CATALOG_MODE=remote
TVSCREENER_LAKEHOUSE_CATALOG_REMOTE_URI=...
TVSCREENER_LAKEHOUSE_CATALOG_REMOTE_WAREHOUSE=...
```

## Implementation Notes
- `LakehouseManager` MUST be initialized from layered settings.
- `get_manager(config_path=...)` SHOULD accept an optional YAML path and use it only for the first
  initialization to avoid swapping catalogs mid-process.
- Local mode should provision directories; remote mode should not attempt to create warehouse paths.

## Risks / Trade-offs
- If multiple components initialize the singleton with different config paths, only the first wins.
  Mitigation: initialize early in the CLI and log a warning if a later config path differs.
- Remote warehouses may require additional Iceberg catalog properties (auth/endpoints). Mitigation:
  allow arbitrary `properties` in config and pass them through to `pyiceberg.load_catalog`.

