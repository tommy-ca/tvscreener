# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

## Proposal: Add macro/market risk opportunity scanner (NQ/ES/VIX/DXY)

We want an operator-friendly market risk scan that uses the existing opportunity scanner pipelines and the same Confluence Matrix view.

Purpose:
- Provide a quick "risk-on/risk-off" and USD-tightening signal to contextualize forex/crypto opportunities.
- Run through the same `data` + `analytics` pipelines (Iceberg-backed rerenders) for auditability.

Initial basket (requested):
- Equity index futures: NQ, ES
- Volatility: VIX futures
- USD macro: DXY index

This change package specifies the workflow, artifacts, and interpretation guidance.
