# OpenSpec Instructions (project-local)

Instructions for AI coding assistants using OpenSpec-style spec-driven development **within this repo**.

## Quick checklist
- Search existing work in `docs/openspec/changes/` before creating new proposals.
- Choose a unique, verb-led `change-id`: `add-…`, `update-…`, `remove-…`, `refactor-…`.
- Scaffold a change package:
  - `docs/openspec/changes/<change-id>/proposal.md`
  - `docs/openspec/changes/<change-id>/tasks.md`
  - `docs/openspec/changes/<change-id>/design.md` (optional; see criteria below)
  - `docs/openspec/changes/<change-id>/specs/<capability>/spec.md` (delta specs)
- Write delta specs using:
  - `## ADDED|MODIFIED|REMOVED|RENAMED Requirements`
  - at least one `#### Scenario:` per requirement

## When to create a change package
Create a proposal when you need to:
- Add new capability or workflow
- Make breaking changes (API/schema)
- Change architecture patterns (e.g. multi-timeframe-first redesign)
- Performance/security work that changes behavior

Skip proposals for:
- Pure bug fixes restoring existing behavior
- Typos/format-only changes
- Non-breaking dependency bumps

## When to include `design.md`
Include `design.md` if any apply:
- Cross-cutting change across multiple modules
- New architectural pattern (e.g. separate data vs analytics pipelines)
- New external dependency or data model changes
- Meaningful security/performance trade-offs

## Project-local paths (no global OpenSpec workspace)
- Project context: `docs/openspec/project.md`
- Active changes: `docs/openspec/changes/`

