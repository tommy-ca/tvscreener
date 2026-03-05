## Tasks

## 1. CLI surface
- [ ] 1.1 Add `--pipeline {data,analytics,both}` to `tvscreener/cli.py`
- [ ] 1.2 Thread pipeline mode through orchestrator request model

## 2. Orchestrator behavior
- [ ] 2.1 Opportunity: implement `analytics` mode (query `tvscreener.signals_latest`, render matrix)
- [ ] 2.2 Strategy: implement `analytics` mode (query `tvscreener.signals_latest`, compute strategies, render matrix)
- [ ] 2.3 Implement `both` mode as: data → analytics (no double-render)

## 3. Docs / runbook
- [ ] 3.1 Update `docs/plans/2026-03-03-rerun-forex-scanners-validate-duckdb-plan.md` with split-pipeline commands

## 4. Verification
- [ ] 4.1 Run majors/minors: `--pipeline data` then `--pipeline analytics` for both opportunity and strategy
- [ ] 4.2 Confirm analytics matrix output matches the lakehouse rows (counts, run_id, fetched_at_utc)

