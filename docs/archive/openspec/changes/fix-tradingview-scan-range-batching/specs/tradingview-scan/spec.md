# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## ADDED Requirements

### Requirement: Explicit tickers are not truncated by default range
When `symbols.tickers` is provided, the client SHALL ensure that the request range covers the full ticker list unless
the user explicitly overrides the range.

#### Scenario: Auto-range sizing for explicit tickers
- **GIVEN** a request with `symbols.tickers` length \(N > 150\)
- **AND** the caller did not set a custom range
- **WHEN** the client sends the `/scan` request
- **THEN** the payload includes `range=[0,N]`

#### Scenario: Respect explicit range overrides
- **GIVEN** a request with `symbols.tickers` length \(N\)
- **AND** the caller explicitly sets `range=[a,b]`
- **WHEN** the client sends the `/scan` request
- **THEN** the payload range remains `[a,b]`

