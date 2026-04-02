# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Design: Composable stages

## Overview
We represent the pipeline as two Prefect tasks:

- **Data stage task**: ingestion + feature engineering + Iceberg writes
- **Analytics stage task**: Iceberg reads + artifact writes + Prefect artifacts (optional)

DuckDB semantic tables:
- Analytics stage produces semantic tables via modeled DuckDB queries.
- Prefect Table artifacts are published from these semantic tables (not by reading parquet into pandas).

These tasks can be used directly inside flows:

- `tvscreener-batch` flow executes batch specs
- Optional `both` composition can be achieved by chaining the analytics task with `wait_for=<data future>`

Composition toggle:
- Set `TVSCREENER_PREFECT_COMPOSE_BOTH=1` to compose `pipeline_mode=both` from the stage tasks.

## Mapping to legacy scripts
Legacy scripts in `workflows/prefect/` are the reference implementation for:

- deterministic Prefect artifact keys
- deployment application to a Prefect work pool
- env var injection for artifact publishing

Prefect-native APIs:
- Prefer using the Prefect Python API client (`prefect.client.orchestration.get_client`) for:
  - deployments listing
  - work pool/work queue inspection
  - scheduled work preview (`get_scheduled_flow_runs_for_work_pool`)
- Do not shell out to the Prefect CLI from extensions wrappers.

Server control note:
- Starting/stopping the Prefect OSS server is fundamentally a CLI concern; extensions wrappers may call
  `prefect.cli.server.start/stop` as a best-effort convenience.
- If server control fails (for example, because a server is already bound to the port), operators can run
  `prefect server stop` / `prefect server start` directly.

Extensions equivalents:

- `workflows/prefect/deploy_schedules.py` -> `extensions/src/tvscreener_ext/deploy_schedules.py`
- `workflows/prefect/prefectctl.py` -> `extensions/src/tvscreener_ext/prefectctl.py`
- `workflows/prefect/run_batch.py` -> `extensions/src/tvscreener_ext/prefect/run_batch.py`

## Deterministic identifiers
- Use `params_hash` as the deterministic run identifier.
- Prefer deterministic Prefect artifact keys derived from `PipelineRunSpec`.

## Queue hygiene
On a single work queue, scheduled runs can accumulate and become `Late`, which can delay on-demand deployment runs.

- Use `tvscreener-prefectctl prune-late --work-queue default --older-than-minutes N` to cancel late scheduled runs.
