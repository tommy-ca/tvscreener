# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Proposal: Composable Prefect flows for Track B

## Problem
The extensions Prefect implementation currently treats a pipeline run as a single opaque task that calls the local
runner. This makes it hard to:

- compose `data` and `analytics` stages as explicit Prefect tasks
- build new flows (and future retries) by reusing stage tasks
- clearly map Prefect-native concepts (flow/deployment/work queue) to our pipeline stages

## Goal
Provide a composable Prefect-native interface in the extensions distribution:

- `data` stage is a task
- `analytics` stage is a task
- `both` can be composed from the two tasks (optionally)

## Non-goals
- Rewriting the underlying lakehouse table contracts.
- Changing `PipelineRunSpec` fields or CLI flags.

## Related / prior art
Legacy repo scripts:

- `workflows/prefect/deploy_schedules.py`
- `workflows/prefect/run_batch.py`
- `prefect.yaml`

These are the reference patterns for:

- deterministic artifact keys
- job env injection for Prefect artifacts
- deployment application to a work pool
