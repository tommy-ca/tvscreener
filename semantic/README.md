# Semantic Models

This directory holds semantic-model definitions for TVScreener analytics.

Goals:
- Define shared dimensions and measures for operational and decision dashboards.
- Make Prefect table artifacts and DuckDB/Iceberg queries consistent.

Current state:
- Definitions are stored in Sidemantic-compatible YAML.
- Execution/validation is planned but not yet wired into CI in this repo.

Notes:
- The matrix view shown in Prefect artifacts is rendered from the opportunity analytics columns that live in `tvscreener.signals_latest`.
- Some run-level context (e.g. `universe`, `instrument_type`) currently lives in `tvscreener.runs` and may require joins in a future semantic runtime.
