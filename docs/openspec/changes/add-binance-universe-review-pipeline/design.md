# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Design: Review pipeline command

### Command
Add `tvscreener-scan review binance-universes`.

It runs `audit` then `report` using:
- `--audit-out-dir` for the audit outputs
- `--report-out-dir` for the report outputs

### Strict mode
When `--strict` is set, the command exits non-zero if any audited universe reports errors.
