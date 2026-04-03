# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Proposal: DuckDB universe reports for Binance base universes

### Goal
Generate repeatable reports (as artifacts) that summarize and compare Binance universes.

### Output artifacts
Write under `artifacts/reports/binance-universes/<timestamp>/`:
- `report.json` (machine-readable)
- `report.md` (human-readable)
- `rows.parquet` and `summary.parquet` (optional)

Reports include a spot vs perp parity table for universe families.

### CLI
Add a report command:

```bash
uv run tvscreener-scan report binance-universes \
  --in-dir artifacts/audits/binance-universes \
  --out-dir artifacts/reports/binance-universes
```
