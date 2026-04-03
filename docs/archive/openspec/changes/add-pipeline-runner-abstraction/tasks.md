# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Tasks

## 1. Define contracts (no behavior change)
- [x] 1.1 Add `PipelineRunSpec` model (JSON-serializable) + `params_hash` computation
- [x] 1.1.1 Add `spec_version` field (forward-compatible exported JSON)
- [x] 1.2 Add `PipelineRunner` protocol/interface + `RunResult` data model
- [x] 1.3 Add `LocalRunner` implementation that delegates to existing orchestration

## 2. CLI integration (adapter layer)
- [x] 2.1 Add `--runner {local,export}` to `tvscreener-scan`
- [x] 2.2 Implement `--runner export` to write the JSON spec to stdout (shell redirect to file) or a dedicated `--spec-out spec.json`
- [x] 2.3 Keep default `--runner local` behavior unchanged

## 3. External runner adapters (optional, follow-up)
- [ ] 3.1 Add an HTTP submit runner (POST `PipelineRunSpec` to an endpoint)
- [x] 3.2 Provide a lightweight “engine wrapper” example (Prefect/Dagster/Temporal) **outside the core library package**
  - reads a `PipelineRunSpec` JSON file
  - validates via the same Pydantic model
  - executes via `LocalRunner.run(spec)`
  - emits `RunResult` JSON as the workflow task output/artifact
  - uses `params_hash` as an idempotency key / run name
- [x] 3.3 Document that workflow-engine SDKs are optional (no base dependency)

## 4. Verification
- [x] 4.1 Ensure `--runner export` round-trips: spec → local runner → same results
- [ ] 4.2 Confirm analytics-only runner is read-only w.r.t. Iceberg tables (signals_latest max timestamp unchanged)
- [x] 4.3 Confirm wrapper example can run without importing engine SDKs in core library codepaths

