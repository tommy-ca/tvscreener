# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Change: Prefect-first runner wrapper (uv-only)

## Why
The project is moving toward a runner-based execution model where pipeline definition is represented as a
`PipelineRunSpec` and execution is delegated to a runner layer (local or external).

To validate the runner abstraction with a real workflow engine while keeping the core library dependency-free,
we will integrate **Prefect first** via a lightweight wrapper.

This enables:
- durable, retryable execution of **data pipelines** (fetch → Iceberg)
- reproducible re-runs of **analytics pipelines** (Iceberg → matrix view)
- a path to scheduling/parallelism without coupling core logic to an engine

## What changes
- Add a Prefect integration that can execute `PipelineRunSpec` runs using **only `uv` commands**:
  - `uv sync` for dependency resolution
  - `uv run` for execution
- Keep Prefect as an **optional** dependency (enabled via a `prefect` extra), with no engine imports required for
  core library usage.
- Add a repo-local wrapper flow (under `workflows/prefect/`) that:
  - reads `PipelineRunSpec` JSON
  - executes the requested pipeline mode (`data|analytics|both`) as Prefect tasks
  - emits a structured `RunResult` JSON artifact

## Non-goals
- Do not require Prefect Cloud/Server for initial usage (local execution is sufficient).
- Do not introduce a hard dependency on Prefect in the core `tvscreener` package.
- Do not redesign the medallion schemas; this change executes existing pipelines.

## Impact
- Adds a concrete “engine wrapper” reference implementation for the runner abstraction.
- Provides a repeatable, uv-native way to orchestrate runs without global Python or `pip`.

