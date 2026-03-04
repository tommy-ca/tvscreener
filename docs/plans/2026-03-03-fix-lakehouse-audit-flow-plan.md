---
title: Lakehouse Audit Flow
type: fix
date: 2026-03-03
---

# Lakehouse Audit Flow

## Overview

This plan phases out legacy repository-local snapshot artifacts, relies solely on the Iceberg lakehouse, and replays both opportunity and strategy scans (matrix view default) so the analytical signal audit is grounded in Snowflake-grade medallion data.

## Problem Statement

- Repository-local snapshots (historically stored as ad-hoc parquet/text files) can drift from the Iceberg-backed
  `tvscreener.gold` table and mislead audits.
- EURCHF and other signals need fresh multi-timeframe validation directly from Iceberg to prove their
  direction, confluence, and scoring attributes.
- The default operator workflow must be lakehouse-first: scans write to Iceberg, audits query Iceberg,
  and any on-disk snapshot is explicitly requested as a debugging artifact.

## Brainstorm Context

Found brainstorm from 2026-03-02: `lakehouse-medallion-pipeline`. It already argues `tvscreener.gold` is the canonical source, so this plan accelerates the phase where exports become read-only reference material and every scan/review runs against Iceberg.

## Proposed Solution

1. **Remove repository snapshots from the default workflow.** Treat Iceberg as truth and only write
   on-disk snapshots when an operator explicitly provides an output path (e.g. `--output ./snapshots/...`).
2. **Rerun opportunity and strategy scanners (majors/minors) with the matrix view default.** This will replay Fresh data into Bronze → Silver → Gold, ensuring each medallion table (especially Gold) is populated with the latest matrix-ready signals.
3. **Validate and audit the resulting Iceberg rows.** For each EURCHF-equivalent signal (and a representative sample of majors and minors), inspect: direction vs. ensemble score, TF×Factor grid, `TF_CONFLUENCE_LONG/SHORT`, `GRID_ALIGNED/TOTAL`, and derived grades. Use EdgeQueryClient/Narwhals pipelines to prove the matrix view matches the raw data and doc the SQL used.
4. **Document the audit.** Write up the inspection steps/results in the plan or a companion note so other engineers can reproduce the lakehouse-backed review.

## Reference Material

- `docs/audit/lakehouse-audit-flow.md` captures the cleanup commands, matrix reruns, and audit SQL referenced by this plan.
- `README.md` now highlights the Lakehouse Audit Flow and links back to this plan and reference document to keep the lakehouse-first expectations visible.

## Tasks

1. **Remove repository snapshots from the default workflow.** Archive/delete local snapshot artifacts,
   update docs to make Iceberg the default, and ensure scans do not produce on-disk files unless an
   explicit `--output` path is provided.
2. **Trigger fresh scans.** Run `uv run tvscreener-scan --scanner opportunity --universe majors --matrix` (and minors), then the same for strategy. Confirm each run completes without snapshot-output errors and that the Gold table reflects the new snapshot via `pyiceberg`/EdgeQuery.
3. **Audit lakehouse rows.** For EURCHF and a handful of matrix entries, capture the SQL/Narwhals expressions used to fetch direction, multi-TF values, and confluence counters. Record the outputs in the plan (tables or summarized tuples) and note any discrepancies between matrix output and raw data.
4. **Update docs/plan/todos.** Ensure the audit results and the new lakehouse-first flow are captured in documentation so future reviewers know not to trust exports.

## Acceptance Criteria

- [ ] Default scans and audits are **Iceberg-first** and do not depend on repository-local snapshots.
- [ ] Any on-disk snapshot is written only when an operator explicitly requests `--output ./snapshots/...` (or another explicit path).
- [x] Opportunity and strategy scans rerun and write fresh rows to `tvscreener.gold` for majors and minors, still showing the matrix default output in CLI logs.
- [x] Lakehouse queries (DuckDB EdgeQueryClient or Narwhals) can reproduce the matrix view values for EURCHF (direction short, `TF_CONFLUENCE_SHORT=3`, `ENSEMBLE_SCORE<0`, etc.) and align with the decorated matrix output.
- [x] Documentation references `Lakehouse Audit Flow` plan and mentions Iceberg tables as the canonical signal source.

## Next Steps

- Replay the commands in `docs/audit/lakehouse-audit-flow.md` to refresh the lakehouse tables and capture new `tvscreener.gold` snapshots.
- Apply the audit SQL against the refreshed data, record the results in this plan, and highlight any discrepancies between the matrix view and the raw rows.
- Archive or delete any remaining repository-local snapshot files once the audit notes are stored.

## Audit Results (2026-03-03)

### Data refresh timestamp (this round)

- Recorded at (UTC): `2026-03-03T14:29:37.881030+00:00`
- Iceberg snapshots (UTC):
  - `tvscreener.bronze`: snapshot `3896887097386602513` @ `2026-03-03T14:29:13.944000+00:00`
  - `tvscreener.silver`: snapshot `2532718628788209061` @ `2026-03-03T14:29:15.378000+00:00`
  - `tvscreener.gold`: snapshot `167056174105696462` @ `2026-03-03T14:29:17.328000+00:00`
  - `tvscreener.gold` latest: `signal_date=2026-03-03`, `PAIR` count = `23`

### Scanner reruns (matrix view)

- Opportunity majors: `uv run tvscreener-scan --scanner opportunity --universe majors --matrix`
- Opportunity minors: `uv run tvscreener-scan --scanner opportunity --universe minors --matrix`
- Strategy majors: `uv run tvscreener-scan --scanner strategy --universe majors --matrix`
- Strategy minors: `uv run tvscreener-scan --scanner strategy --universe minors --matrix`

After reruns, `tvscreener.gold` contains 23 unique forex pairs for `signal_date=2026-03-03` (majors + minors) and remains queryable via the Iceberg catalog.

### EURCHF spot check (Iceberg vs matrix)

Iceberg (`tvscreener.gold`, `signal_date=2026-03-03`) for `PAIR='EURCHF'`:

- `DIRECTION=short`
- `TF_CONFLUENCE_SHORT=3`, `TF_CONFLUENCE_LONG=0`
- `TOTAL_CONFLUENCE=10`, `GRID_ALIGNED=10`, `GRID_TOTAL=12`
- `ENSEMBLE_SCORE<0` (observed `-0.456438`)
- `GRADE=A+`

These values match the matrix output shown in the scanner rerun logs.

### Pipeline note: overwrite safety

Observed during this audit: with overwrite-by-date semantics, running minors after majors would replace the entire `(asset_type, signal_date)` partition, dropping majors from `tvscreener.gold`. The write path now scopes overwrite filters to the scanned `PAIR` set so majors + minors can coexist for the same date.

### Tests

- `uv run pytest tests/test_analytics_pipeline.py -v` (2 passed)
- `uv run pytest tests/unit/test_forex_opportunity.py tests/unit/test_forex_strategy.py -v` (45 passed)
