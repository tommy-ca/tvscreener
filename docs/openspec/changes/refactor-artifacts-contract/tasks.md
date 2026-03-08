# Tasks: Refactor artifacts contract

- [ ] Inventory current writers (local runner, Prefect runner, batch runner)
- [ ] Define v2 artifacts contract (delta spec)
- [x] Update Prefect runner to write `artifacts/runs/<params_hash>/` (alias old dir)
- [x] Update batch runner to emit a single `run_result.json` for all modes
- [x] Deprecate stage-specific result JSON files (`run_result_data.json`, `run_result_analytics.json`)
- [ ] Add a maintenance command to prune/migrate deprecated artifacts
- [ ] Add tests asserting artifact filenames and payload fields
