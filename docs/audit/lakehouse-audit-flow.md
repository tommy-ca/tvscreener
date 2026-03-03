---
title: Lakehouse Audit Flow Reference
type: guide
date: 2026-03-03
---

# Lakehouse Audit Flow Reference

## Purpose

The Lakehouse Audit Flow phases out legacy `exports/` snapshots and relies solely on the Iceberg medallion tables (`tvscreener.bronze`, `tvscreener.silver`, `tvscreener.gold`) as the canonical signal sources. This reference captures the concrete steps for cleaning exports, replaying matrix-first scans, running SQL audits, and keeping a reproducible log of what was inspected so downstream reviewers never have to guess which dataset is authoritative.

## Step 1: Treat `exports/` as reference-only

- Move any historical `exports/*.parquet` or related `.txt` files into an archival path (for example, `exports/archive/2026-03-03/`) so the root `exports/` directory only contains intentionally captured snapshots for manual reference. Use `mv`, `zip`, or `rsync` to archive the files with a timestamp.
- Update operators that the default DataOps/MLOps pipeline writes directly into Iceberg and that `exports/` receives exports only when `--output exports/...` **and** `--write-exports` (opt-in flag in custom tooling) are intentionally requested.
- Document the archive location and the policy in `README.md` and this guide so new reviewers see the rules before running scans.

## Step 2: Replay scanners with the matrix view default

Run each scanner with `uv run tvscreener-scan` while relying on the matrix view defaults (`--matrix` is implied when no view flag is provided). Example sequence:

```bash
uv run tvscreener-scan --scanner opportunity --universe majors --matrix
uv run tvscreener-scan --scanner opportunity --universe minors --matrix
uv run tvscreener-scan --scanner strategy --universe majors --matrix
uv run tvscreener-scan --scanner strategy --universe minors --matrix
```

After each run:

1. Confirm the CLI logs show matrix output and that no new `exports/` files were written without explicit `--output`/`--write-exports` usage.
2. Use `pyiceberg` or an EdgeQuery pipeline to query `tvscreener.gold` and prove the new snapshot exists. For example:

```python
from tvscreener.lib.lakehouse import get_catalog

catalog = get_catalog()
table = catalog.load_table("tvscreener.gold")
rows = table.scan(limit=1).to_arrow().to_pandas()
print(rows)
```

3. Record the snapshot ID or timestamp so auditors can retrace what data the CLI produced.

## Step 3: Audit the Iceberg rows against the matrix view

The goal of the audit is to prove the decorated matrix view matches the raw Iceberg data for high-confluence signals like EURCHF.

### Sample SQL audit

```sql
SELECT
  signal_date,
  PAIR,
  DIRECTION,
  ENSEMBLE_SCORE,
  TOTAL_CONFLUENCE,
  GRID_ALIGNED,
  GRID_TOTAL,
  TF_CONFLUENCE_LONG,
  TF_CONFLUENCE_SHORT,
  TF_CONFLUENCE_EMA2024,
  TF_CONFLUENCE_RSI144
FROM tvscreener.gold
WHERE PAIR = 'EURCHF'
ORDER BY signal_date DESC
LIMIT 5;
```

Use `EdgeQueryClient` to run this query and compare the values with the Matrix renderer logs. An example Python snippet:

```python
from tvscreener.lib.query import EdgeQueryClient

with EdgeQueryClient() as client:
    df = client.query_sql(
        "tvscreener.gold",
        """
        SELECT PAIR, DIRECTION, ENSEMBLE_SCORE, TOTAL_CONFLUENCE,
               GRID_ALIGNED, GRID_TOTAL, TF_CONFLUENCE_LONG,
               TF_CONFLUENCE_SHORT
        FROM tvscreener.gold
        WHERE PAIR = 'EURCHF'
        ORDER BY signal_date DESC
        LIMIT 10
        """,
    )
    print(df)
```

If confluence counts, grid totals, and ensemble scores align with the CLI matrix output (especially the direction and `TF_CONFLUENCE_LONG/SHORT` columns), the lakehouse rows are validated.

## Step 4: Record and share the audit

- Log each audit session directly in `docs/plans/2026-03-03-fix-lakehouse-audit-flow-plan.md` or a linked note so other engineers can reproduce it. Include the SQL used, the `EdgeQueryClient` library calls, and any `pyiceberg` snapshot IDs.
- Link this guide from the README and plan documents to keep the lakehouse-first policy visible.
- Bookmark the `tvscreener.gold` table as the single source of truth; any future CLI flag or script that touches `exports/` must explicitly mention the `--write-exports` opt-in and the reference-only policy.
