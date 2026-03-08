# Tasks: Refactor lakehouse namespace layout

- [ ] Decide canonical `instrument_type` enums per asset type (forex/crypto/futures)
- [ ] Add logical->physical table id resolver (nested namespaces vs flattened encoding)
- [ ] Introduce crypto spot/perp stage tables under the new layout
- [ ] Add compatibility aliases for existing `tvscreener.*` tables (forex default)
- [ ] Update docs/specs and rerun plans to reference the new identifiers
- [ ] Add audit tooling to verify isolation (no cross-instrument overwrite)
