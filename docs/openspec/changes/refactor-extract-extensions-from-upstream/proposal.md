# Proposal: Extract extensions distribution from upstream

## Goal
Package repo-local orchestration (Prefect scheduling, batch tooling) and any custom screeners as a separate
extensions distribution that depends on an installed upstream `tvscreener` package.

This proposal MUST account for the current upstream package-index surface area and may require either:

- publishing a new upstream version with the workflow/pipeline surface area this repo uses, OR
- implementing the workflow/pipeline surface area in the extensions distribution.

## Motivation
- Reduce long-lived forks and patching of upstream.
- Make Prefect scheduling + artifacts reproducible on any machine with `uv`.
- Ensure workflows can run in CI/ops environments without cloning this repo.

## Non-goals
- Changing the on-disk artifacts contract.
- Redesigning the Iceberg medallion tables.

## Success criteria
- Extensions install with `uv` (no global Python / no `pip`).
- Extensions run against an installed upstream `tvscreener` (no import shadowing from a repo checkout).
- Essential pipelines (forex majors/minors; Binance spot/perp majors/minors; market risk) run via Prefect and write:
  - Iceberg tables (data)
  - DuckDB-powered analytics outputs (analytics)
  - `artifacts/runs/<params_hash>/run_spec.json` + `run_result.json`

## Current blocker (2026-03-25)
The package index `tvscreener==0.2.1` does not ship `tvscreener-scan`, `tvscreener.cli`, or the repo-local pipeline
modules (`tvscreener.lib.*`). Extensions therefore cannot be a thin wrapper unless upstream publishes those modules.

Decision: proceed with Track B (extensions-owned pipelines).
