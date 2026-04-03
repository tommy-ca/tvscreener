# workflow-manager

## Description
Management of Prefect orchestration components, including server, deployments, workers, and run pruning.

## Instructions
When this skill is activated, you MUST help the user manage their Prefect orchestration layer:

1.  **Server Management**:
    - Check if the Prefect server is running: `curl -s http://127.0.0.1:4200/api/health`.
    - Offer to start/stop the server using `tvscreener-prefectctl server start/stop`.

2.  **Deployment & Queue Status**:
    - Offer to check work pool and queue status: `uv run --project extensions --extra prefect tvscreener-prefectctl check`.
    - Report on number of scheduled runs and their status (Pending, Late, etc.).

3.  **Worker Control**:
    - Offer to start a worker for a specific queue (e.g., `data` or `analytics`).
    - Command: `uv run --project extensions --extra prefect tvscreener-prefectctl worker --queue <name> --limit <n>`.

4.  **Run Pruning**:
    - Offer to cancel late flow runs to clear the queue.
    - Command: `uv run --project extensions --extra prefect tvscreener-prefectctl prune-late --older-than-minutes 30`.

5.  **Artifact Inspection**:
    - List recent Prefect artifacts (markdown matrices or tables).
    - Command: `uv run --project extensions --extra prefect tvscreener-prefectctl artifacts --limit 10`.

## Available Resources
- `tvscreener-prefectctl`: Central CLI for Prefect orchestration.
- `tvscreener-deploy-schedules`: Tool for applying batch deployments.
- `docs/openspec/project.md`: Orchestration definitions and task stage logic.
