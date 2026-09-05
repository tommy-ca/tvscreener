# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Tasks: Crypto opportunity scanning presets

- [x] Define majors/minors universes for Binance spot/perp
- [x] Ensure `--universe majors|minors` maps correctly for crypto
- [x] Document recommended opportunity scanning presets
- [x] Document audit/readiness checks via DuckDB report
- [x] Validate sequential `--pipeline data` then `--pipeline analytics --matrix` rerenders for spot/perp majors/minors
- [x] Validate `--runner prefect` parity runs for spot/perp majors/minors
