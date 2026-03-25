# Tasks: Extract extensions distribution from upstream

## Packaging
- [x] Add `extensions/` uv project (its own `pyproject.toml`).
- [x] Create extensions Python package (e.g. `tvscreener_ext`).
- [x] Add CLI entrypoints:
  - [x] `tvscreener-ext-scan` (extensions-owned pipeline runner)
  - [x] `tvscreener-prefectctl` (server/pool/queues/workers helper)
  - [x] `tvscreener-deploy-schedules` (apply deployments + runner start)
  - [x] `tvscreener-ext-validate` (essential validation runset)
  - [x] `tvscreener-ext-audit` (lakehouse audit helper)

## Upstream-only execution
- [x] Ensure `uv run --project extensions ...` resolves `tvscreener` from site-packages (not repo-local sources).
- [x] Add a guard script (CI/pre-commit) that fails if `tvscreener` resolves to the repo checkout when running under `extensions/`.

## Upstream surface area
- [x] Decide strategy for missing upstream workflow surface area: Track B (extensions-owned pipelines)

## Track B: Extensions-owned pipelines
- [x] Implement `PipelineRunSpec` + runner in `tvscreener-ext`.
- [x] Implement Iceberg persistence (catalog + table writes/reads) in `tvscreener-ext`.
- [x] Implement DuckDB-backed analytics outputs in `tvscreener-ext`.
- [x] Implement Prefect flows on top of extensions runner (`run_batch`, deployments).

## Workflow migration
- [ ] Move `workflows/prefect/*` logic into extensions package (keep repo-local thin wrappers temporarily).
- [ ] Update docs/runbooks to prefer `uv run --project extensions ...` commands.

## Validation
- [x] Prefect server + in-process runner: rerun essential universes with `--pipeline both`.
- [ ] Prefect server + workers: validate scheduled runs (requires READY deployments via image/remote storage).
- [ ] Iceberg validation: verify expected tables updated (`bronze`, `signals_latest`, `runs`).
- [ ] DuckDB validation: verify analytics outputs can be produced from Iceberg inputs.

## Environment parity
- [x] Default Prefect work queue is `default` and encoded in deployments.
- [x] Default lakehouse base dir is repo-local (`.tvscreener/lakehouse`) with env override.

## Scheduling
- [x] Add split deployments (data + analytics) for forex + binance universes.

## Worker packaging
- [ ] Adopt a Prefect 3 worker deployment packaging strategy (image or remote storage) so deployments become `READY`.
