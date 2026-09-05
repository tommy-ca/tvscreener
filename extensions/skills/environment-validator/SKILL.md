# environment-validator

## Description
Ensures the local development environment is healthy, compliant with the Zero-Fork policy, and that orchestration components (Prefect) are operational.

## Instructions
When this skill is activated, you MUST perform the following health checks:

1.  **Zero-Fork Compliance**:
    - Run the import audit script: `uv run --project extensions python extensions/tools/check_upstream_tvscreener_resolution.py`.
    - If it fails, report that the local `tvscreener/` source is shadowing the installed package.

2.  **Orchestration Health**:
    - Check Prefect server connectivity: `curl -s http://127.0.0.1:4200/api/health`.
    - Check work pool and queue status: `uv run --project extensions --extra prefect tvscreener-prefectctl check`.
    - Report any `NOT_READY` deployments or missing workers.

3.  **Workspace Hygiene**:
    - Check for accumulated artifacts: `du -sh artifacts/`.
    - Identify if any gitignored files are being tracked: `git ls-files --others --exclude-standard`.
    - Check disk space in the project directory.

4.  **Test Stability**:
    - Run a representative set of unit tests: `uv run --project extensions python -m pytest tests/unit/test_api_validation.py tests/unit/test_field_conditions.py`.

5.  **Summary**:
    - Provide a "Health Report" with a PASS/FAIL status for each category.
    - Propose remediation steps for any failures (e.g., `tvscreener-prefectctl server start`, `scripts/clean-workspace.sh`).

## Available Resources
- `extensions/tools/check_upstream_tvscreener_resolution.py`: Validates upstream library resolution.
- `tvscreener-prefectctl`: CLI for Prefect orchestration management.
- `scripts/clean-workspace.sh`: Script for deep workspace cleanup.
