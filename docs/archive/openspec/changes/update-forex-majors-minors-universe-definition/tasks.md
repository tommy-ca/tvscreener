# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

# Tasks: Forex majors/minors universe definition

- [x] Specify the fixed majors list
- [x] Specify minors as USD-excluding crosses
- [x] Expand minors to full 21-cross coverage (ex-USD majors currencies)
- [x] Document pre-analytics filtering (exchange expansion, contract type filter, dedup)
- [x] Add unit test to prevent drift
- [x] Validate Prefect `data` then `analytics --matrix` rerun for majors/minors
