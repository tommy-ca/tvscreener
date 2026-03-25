# Proposal: Standardize terms and interfaces

## Problem
Project docs and operator runbooks currently mix:

- MLOps/DataOps vocabulary (feature engineering, feature tables)
- Iceberg medallion naming (bronze/silver/gold)
- Prefect-native naming (flow/deployment/work pool/work queue/worker/artifact)

This creates ambiguity about what each pipeline stage does, what is read-only vs write, and which Prefect concepts
map to our CLIs.

## Goal
Define a single, canonical vocabulary and interface contract for:

- pipeline stages (`pipeline_mode`)
- lakehouse tables (Iceberg identifiers)
- orchestration objects (Prefect)
- artifacts (filesystem vs Prefect artifacts)

## Non-goals
- Renaming existing user-facing CLI flags or breaking existing `PipelineRunSpec` fields.
- Changing Iceberg table identifiers in this change.

## Approach
Add an OpenSpec “Terminology” delta spec and update existing OpenSpec docs to use it.
