# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Tasks

## 1. CLI surface
- [x] 1.1 Add `--pipeline {data,analytics,both}` to `tvscreener/cli.py`
- [x] 1.2 Thread pipeline mode through orchestrator request model

## 2. Orchestrator behavior
- [x] 2.1 Opportunity: implement `analytics` mode (query `tvscreener.signals_latest`, render matrix)
- [x] 2.2 Strategy: implement `analytics` mode (query `tvscreener.signals_latest`, compute strategies, render matrix)
- [x] 2.3 Implement `both` mode as: data → analytics (no double-render)

## 3. Docs / runbook
- [ ] 3.1 Update `docs/plans/2026-03-03-rerun-forex-scanners-validate-duckdb-plan.md` with split-pipeline commands
  - follow-up: fold in Prefect batch runbook references from `workflows/prefect/README.md`

## 4. Verification
- [ ] 4.1 Run majors/minors: `--pipeline data` then `--pipeline analytics` for both opportunity and strategy
- [ ] 4.2 Confirm analytics matrix output matches the lakehouse rows (counts, run_id, fetched_at_utc)
- [ ] 4.3 Prefect parity smoke (local): run the same majors/minors runs with `--runner prefect` and confirm artifacts

