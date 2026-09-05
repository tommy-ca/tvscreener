# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Tasks

## 1. Requirements/specs/design
- [x] Add delta spec for matrix view snapshot label
- [x] Document snapshot derivation (min/max `fetched_at_utc`) and fallback behavior

## 2. Implementation
- [x] Compute snapshot label for opportunity analytics runs and pass to renderer
- [x] Compute snapshot label for strategy analytics runs and pass to renderer
- [x] Update Rich renderer to append snapshot label to matrix titles when provided

## 3. Verification
- [x] Run `--pipeline analytics --matrix` for forex majors and confirm the header includes `Snapshot: ...`
- [x] Run `--pipeline analytics --matrix` for forex minors and confirm the header includes a range when applicable
- [ ] (Optional) Add a unit test for snapshot label formatting (future)

