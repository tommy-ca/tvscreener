# Brainstorm: Gemini CLI Skills for tvscreener

This document explores the creation of specialized "Skills" for the Gemini CLI to automate and guide professional workflows in the `tvscreener-ext` environment.

## 1. Skill: `market-scanner`
**Purpose**: Execute end-to-end scans with guided configuration.
- **Workflow**:
    1. Ask for asset type (forex, crypto, stock).
    2. Ask for universe (majors, minors, top100, etc.).
    3. Ask for execution mode (local, prefect).
    4. Execute `tvscreener-ext-scan` with the selected parameters.
    5. Optionally open the results (Parquet/JSON).

## 2. Skill: `lakehouse-auditor`
**Purpose**: Inspect and audit the Medallion lakehouse.
- **Workflow**:
    1. List active Iceberg tables.
    2. Run `tvscreener-ext-audit` for universe health.
    3. Allow natural language queries (translated to SQL via DuckDB).
    4. Provide summaries of data freshness.

## 3. Skill: `workflow-manager`
**Purpose**: Manage Prefect deployments and workers.
- **Workflow**:
    1. Check status of Prefect server.
    2. List scheduled runs.
    3. Prune late runs.
    4. Start/Stop workers for specific queues (`data`, `analytics`).

## 4. Skill: `strategy-developer`
**Purpose**: Guide the implementation of new technical indicators or strategies.
- **Workflow**:
    1. Provide templates for new `Field` or `Screener` subclasses.
    2. Guide the update of `ConfigFactory` and `ScanWorkflow`.
    3. Automate the creation of test suites for the new strategy.

## 5. Skill: `environment-validator`
**Purpose**: Ensure the local environment is healthy and zero-fork compliant.
- **Workflow**:
    1. Run `check_upstream_resolution.py`.
    2. Run full test suite.
    3. Verify Prefect server accessibility.
    4. Check for disk space/artifact accumulation.

## Implementation Plan
1.  **Skill Definitions**: Create `extensions/skills/<name>/SKILL.md` files.
2.  **Tool Mapping**: Map existing extensions CLIs to skill instructions.
3.  **Activation**: Configure the repository to automatically suggest these skills when relevant keywords are detected.
