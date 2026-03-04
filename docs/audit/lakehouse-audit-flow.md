---
title: Lakehouse Audit Flow (Iceberg-first)
type: guide
date: 2026-03-03
---

# Lakehouse Audit Flow (Iceberg-first)

## Purpose

This runbook defines the **canonical** audit workflow for `tvscreener`:

- The Iceberg medallion tables are the source of truth: `tvscreener.bronze`, `tvscreener.silver`, `tvscreener.gold`.
- Audits MUST be reproducible from Iceberg snapshots and recorded with the SQL used.
- On-disk snapshots are **optional** operator artifacts and MUST NOT be required for correctness.

## Policy (read this first)

- **Canonical**: Iceberg tables (`tvscreener.*`) are the only canonical source.
- **Default behavior**: running scans should not produce repository-local snapshot files.
- **Optional snapshots**: when you need a local “frozen” artifact for debugging, write it explicitly using
  `--output ./snapshots/...` (or another directory under the working directory). Do not treat those
  files as authoritative.

## Step 1: Replay scanners (matrix-first)

Run each scanner with `uv run tvscreener-scan` while relying on the matrix view defaults (`--matrix` is implied when no view flag is provided). Example sequence:

```bash
uv run tvscreener-scan --scanner opportunity --universe majors --matrix
uv run tvscreener-scan --scanner opportunity --universe minors --matrix
uv run tvscreener-scan --scanner strategy --universe majors --matrix
uv run tvscreener-scan --scanner strategy --universe minors --matrix
```

If you are not using the default config location, add `--config tvscreener.yaml` (or your YAML path) to the scan commands.

After each run:

1. Confirm the CLI logs show matrix output.
2. Confirm the lakehouse tables have fresh snapshots (query Iceberg, not files).

## Step 2: Confirm Iceberg snapshots exist (Bronze/Silver/Gold)

Use `pyiceberg` to prove a fresh snapshot exists:

```python
from tvscreener.lib.lakehouse import get_catalog

catalog = get_catalog()
table = catalog.load_table("tvscreener.gold")
rows = table.scan(limit=1).to_arrow().to_pandas()
print(rows)
```

Record the `snapshot_id` values (Bronze/Silver/Gold) in your audit entry.

You can also validate via the CLI query subcommand:

```bash
# NOTE: `query` must be the first token after `tvscreener-scan`.
# If you pass `--config`, place it at the end.
uv run tvscreener-scan query tvscreener.gold --sql "SELECT signal_date, PAIR, DIRECTION, ENSEMBLE_SCORE, TOTAL_CONFLUENCE, GRID_ALIGNED, GRID_TOTAL, TF_CONFLUENCE_LONG, TF_CONFLUENCE_SHORT FROM df ORDER BY signal_date DESC LIMIT 25" --head 25 --config tvscreener.yaml
```

## Step 3: Audit Iceberg rows against the matrix view

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

## Optional: write a local snapshot (non-canonical)

If you need a debugging artifact you can re-open later, write it explicitly:

```bash
uv run tvscreener-scan --scanner opportunity --universe majors --matrix --output ./snapshots/majors_opportunity.parquet
```

This snapshot is **not** the source of truth. Always cite Iceberg snapshot IDs in audit records.

## Step 4: Record and share the audit (required)

- Log each audit session directly in `docs/plans/2026-03-03-fix-lakehouse-audit-flow-plan.md` (or a linked note).
- Include the SQL used, the `EdgeQueryClient`/`pyiceberg` calls, and the Iceberg `snapshot_id`s.
- Link this guide from the README and plan documents to keep the lakehouse-first policy visible.
- Bookmark `tvscreener.gold` as the single source of truth for signals.

### Audit record template (copy/paste)

```text
Audit timestamp (UTC):
Run commands:
- ...

Iceberg snapshot IDs (UTC):
- tvscreener.bronze: snapshot <id> @ <timestamp>
- tvscreener.silver: snapshot <id> @ <timestamp>
- tvscreener.gold: snapshot <id> @ <timestamp>

Spot checks:
- Pair(s): ...
- SQL:
  SELECT ...

Expected invariants:
- Matrix direction == Iceberg DIRECTION
- Grid totals and confluence counters match

Notes / discrepancies:
- ...
Follow-ups:
- ...
```
