# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Proposal: Document forex majors/minors universe contract

Forex `majors`/`minors` are core operator workflows and are referenced as the UX baseline for crypto.

This change package documents the deterministic universe contract and the pre-analytics filtering behavior:
- `majors` is a fixed, curated list of the most liquid USD pairs.
- `minors` is a fixed list of liquid crosses that exclude `USD`.
- Before analytics ranking, the forex screener expands pairs across preferred exchanges, filters by contract type, and deduplicates to one row per `PAIR`.

No behavior changes are intended; this is specification + documentation + a small unit test to prevent drift.
