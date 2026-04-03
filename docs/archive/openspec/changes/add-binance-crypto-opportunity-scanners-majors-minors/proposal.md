# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Proposal: Binance crypto opportunity scanners (majors/minors)

### Goal
Define a forex-like operating model for crypto opportunity scanning on Binance using `majors`/`minors` universes.

### Why
- Operators already understand the forex workflow: `majors` for default scans, `minors` for breadth.
- Crypto needs the same ergonomics while keeping universe selection tradeable-first and reproducible.

### Scope
- Document recommended CLI presets for:
  - spot majors/minors
  - perp majors/minors
- Define readiness checks and which DuckDB report sections to use.

### Non-goals
- No new scoring model in the opportunity scanner.
- No strategy-specific ranking logic added at selection time.
