## 1. Documentation (lakehouse-first runbook + audit ledger)
- [x] 1.1 Rewrite `docs/audit/lakehouse-audit-flow.md` as an Iceberg-first runbook
  - [x] Replace any “archive `exports/`” guidance with “no repository snapshots by default”
  - [x] Add an “Optional snapshots” subsection using `--output ./snapshots/...` examples
  - [x] Add a copy/paste “Audit Record Template” (run metadata + snapshot IDs + SQL)
- [ ] 1.2 Refactor `docs/plans/2026-03-03-fix-lakehouse-audit-flow-plan.md` into an audit ledger
  - [ ] Add a section for “Discrepancies + follow-ups” per audit session
  - [x] Update acceptance criteria to align with “no exports by default”
- [x] 1.3 Update `docs/plans/2026-03-03-rerun-forex-scanners-validate-duckdb-plan.md`
  - [x] Ensure all validation examples use Iceberg identifiers (already mostly true)
  - [x] Add a note that snapshots are optional and not required
- [x] 1.4 Audit and correct `docs/plans/2026-03-03-multi-asset-iceberg-catalog-and-table-design-plan.md`
  - [x] Add “Current implementation status (as of branch HEAD)”
  - [x] Fix outdated partitioning claims (Bronze includes `asset_type` + `timeframe_set_id`)
  - [x] Fix overwrite scoping claim (now prefers `entity_id` when available)
  - [x] Clarify health validation reality (pandera schema file exists but pipeline gating is in code)
- [x] 1.5 Update `README.md` “Lakehouse Audit Flow” section for the new policy

## 2. OpenSpec (requirements + design)
- [x] 2.1 Ensure the change package is complete:
  - [x] `proposal.md` reflects the final doc + behavior expectations
  - [x] `specs/lakehouse-audit-flow/spec.md` includes scenarios for every requirement
  - [x] `design.md` documents the Iceberg-first decisions and audit record format

## 3. Follow-up code work (to enforce docs; do after doc approval)
- [ ] 3.1 Remove repository snapshot defaults from edge analytics
  - [x] Update `tvscreener/lib/query.py` default DuckDB cache path to `~/.tvscreener/...` (not repo)
  - [ ] Add a regression test to ensure `EdgeQueryClient()` does not create `exports/`
- [ ] 3.2 Make “snapshot directory” writes explicitly intentional (only if we reserve a folder name)
  - [ ] Add an opt-in flag (e.g. `--write-snapshots`) to `tvscreener/cli.py`
  - [ ] Enforce gating in `tvscreener/lib/orchestrator.py` before creating parent dirs
  - [ ] Update MCP tool docs in `tvscreener/mcp/server.py` and `tvscreener/mcp/tools.py`
- [ ] 3.3 Validate that `scanner_family` is set correctly for each scanner type
  - [ ] Ensure opportunity vs strategy scans persist correct `scanner_family` in medallion outputs

## 4. Verification (runbook)
- [ ] 4.1 Run the scan + query sequence from `docs/audit/lakehouse-audit-flow.md`
- [ ] 4.2 Run:
  - [x] `uv run pytest tests/test_analytics_pipeline.py -v`
  - [ ] `uv run pytest tests/unit/test_forex_opportunity.py tests/unit/test_forex_strategy.py -v`

