# [LEGACY DOCUMENTATION]

> **Note**: This document is preserved for historical context. Its contents may refer to deprecated directories (`workflows/`, `semantic/`, `todos/`) or outdated architectural patterns. For the current authoritative project specification, refer to `docs/openspec/project.md` and `docs/architecture/`.

---

---
date: 2026-02-28
topic: parquet-export-with-embedded-metadata
---

# Parquet Export with Embedded Metadata

## What We're Building
We are updating the Parquet export functionality in the Forex scanners to include detailed execution metadata embedded directly within the file header, and enriched data columns in the table itself. 

Currently, the Parquet output is a simple table with a separate `.meta.json` sidecar file. This change will:
1.  **Enrich Table Data**: Include "visual" columns like `GRADE` and `STRENGTH_SIGN` (e.g., `++`, `+`) in the Parquet file to ensure the exported data matches the richness of the CLI output.
2.  **Embed Metadata**: Use `pyarrow` to store comprehensive metadata in the Parquet file's schema header. This metadata will include:
    *   **Scanner Config**: All filters, universes, and timeframes used.
    *   **Execution Details**: Timestamp, run duration, and environment info.
    *   **Summary Stats**: Total results found and average ensemble scores.
    *   **Raw API Context**: Key details from the underlying TradingView request/response for auditability.

## Why This Approach
We chose **Approach A: Schema Metadata** because it aligns with professional data science practices. Embedding metadata in the file header ensures that the data and its context are never separated, without the inefficiency of adding redundant "global" columns for every row in the table. 

By including the "enriched" columns in the table data, we make the file "ready-to-use" for downstream analysis or reporting without requiring the user to re-implement the grading logic.

## Key Decisions
- **PyArrow Integration**: We will shift from basic `df.to_parquet` to using `pyarrow.Table.from_pandas` and `pyarrow.parquet.write_table` to gain granular control over the metadata field.
- **JSON Serialization**: Detailed metadata dictionaries will be serialized to a JSON string and stored under a custom key (e.g., `tvscreener_metadata`) in the Parquet schema.
- **Sidecar Removal**: For Parquet files specifically, the redundant `.meta.json` sidecar file will be deprecated or removed since the data is now embedded.
- **Enriched Columns**: The export process will ensure that `calculate_grades` and strength indicators are applied to the DataFrame before serialization.

## Open Questions
- Should we provide a utility command (e.g., `tvscreener-inspect`) to easily read the embedded metadata from a Parquet file without needing a custom script?
- Should we keep the sidecar file as an optional fallback for users who prefer raw JSON access?

## Next Steps
→ `/workflows:plan` for implementation details in `export_helpers.py` and updating the scanner export calls.
