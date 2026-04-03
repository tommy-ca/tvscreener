# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
title: Enhanced Parquet export with embedded metadata and enriched columns
type: feat
date: 2026-02-28
---

# Enhanced Parquet export with embedded metadata and enriched columns

## Overview
Update the Parquet export functionality to embed detailed execution metadata (Scanner Config, Execution Details, Summary Stats, Sanitized API Summary) directly into the Parquet file header using `pyarrow`. Additionally, ensure that enriched table data (visual symbols and grades) are included as standard columns in the export.

## Problem Statement / Motivation
Currently, Parquet exports in the Forex scanners are basic tables. While metadata exists, it is stored in a separate `.meta.json` sidecar file, which is easily separated from the data and lacks the richness of the CLI analysis (like grades and strength symbols). By embedding this metadata and enriching the table, we create a self-contained, professional-grade data artifact for downstream analysis.

## Proposed Solution
1.  **Enrich Table Data**: Ensure `GRADE`, `TF_CONFLUENCE`, and `FACTOR_CONFLUENCE` are included in the DataFrame passed to the exporter.
2.  **Metadata Embedding**: Refactor `export_to_parquet` to use `pyarrow` for embedding JSON-serialized metadata into the `schema.metadata` field. 
3.  **Sanitized API Summary**: Instead of raw payloads, capture an audit trail summary (URLs, HTTP Status, specific filters used, and whitelisted headers).
4.  **Sidecar Fallback**: If `pyarrow` is not available, fall back to the existing `.meta.json` sidecar behavior with a warning.

## Technical Considerations
- **PyArrow Optionality**: Use a try/except block for `pyarrow` imports. If missing, use the standard `pandas.to_parquet` and sidecar file.
- **Whitelist Sanitization**: Use a strict whitelist of "safe" headers (e.g., `X-Request-ID`, `Server-Timing`) to avoid leaking secrets like `Cookie` or `Authorization`.
- **Metadata Versioning**: Include a `version: "1.0"` field in the metadata JSON blob for future compatibility.
- **Collector Pattern**: Implement metadata aggregation in the scanner level or a dedicated utility rather than bloating the core `Screener.get()` method.

## Acceptance Criteria
- [x] Parquet files contain `GRADE` and confluence columns.
- [x] Parquet files have embedded metadata readable via `pyarrow.parquet.read_metadata(path).metadata`.
- [x] Metadata includes `version`, `config`, `execution_stats`, and `api_summary`.
- [x] Sidecar `.meta.json` is ONLY created if `pyarrow` is missing.
- [x] API summary is sanitized via whitelist (no secrets/cookies).
- [x] Multiple API calls in a single scan are summarized in the metadata.

## Implementation Plan

### Phase 1: Metadata & Sanitization
- [ ] Create `tvscreener/lib/screeners/metadata_utils.py`:
    - [ ] Implement `MetadataCollector` class to track scan state and API calls.
    - [ ] Implement header whitelisting logic for API summaries.
    - [ ] Add JSON serialization helpers for `numpy` and `datetime` types.

### Phase 2: Capture Context
- [ ] Update `ForexOpportunityScreener` and `ForexStrategyScanner` to use the `MetadataCollector` during the scan process.
- [ ] Aggregate summary info from each parallel API call without storing massive payloads.

### Phase 3: Enhanced Exporter
- [ ] Update `tvscreener/lib/screeners/export_helpers.py`:
    - [ ] Implement `export_to_parquet` with `pyarrow` embedding logic.
    - [ ] Add fallback logic to `pandas.to_parquet` + sidecar if `pyarrow` is unavailable.
    - [ ] Ensure sidecar file is suppressed when embedding succeeds.

### Phase 4: Validation
- [ ] Add unit test verifying metadata extraction from a generated Parquet file.
- [ ] Verify that sensitive headers are NOT present in the embedded metadata.

## References & Research
- Existing implementation: `tvscreener/lib/screeners/export_helpers.py:73`
- Grade calculation: `tvscreener/score.py:calculate_grades`
- PyArrow Metadata Docs: [Storing Metadata in Parquet](https://arrow.apache.org/docs/python/parquet.html#storing-metadata)
