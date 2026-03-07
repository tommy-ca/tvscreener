## Plan: Seamless Prefect runner mode

### Goal
Enable **single-command Prefect execution** from the existing CLI so operators do not need to:
1) export a `PipelineRunSpec` to JSON
2) run a separate Prefect wrapper script

Target UX:

```bash
uv run --extra prefect tvscreener-scan --runner prefect --scanner opportunity --pipeline both ...
```

### Constraints
- Prefect remains an **optional** dependency (installed via `uv sync --extra prefect`).
- Base library usage (`--runner local`) must not require Prefect.

### Steps
- Add `--runner prefect` to `tvscreener-scan`.
- When selected, build `PipelineRunSpec` from CLI args and execute via Prefect flow in-process.
- Ensure artifacts are always written under `artifacts/prefect/<params_hash>/`.

### Acceptance criteria
- The single Prefect command runs without an intermediate spec file.
- Artifacts exist for every run:
  - `run_spec.json`
  - `run_result*.json`
  - default `*_results.parquet` for analytics when `--output` is omitted
- CLI still supports `--runner export` for external engines and `--runner local` for direct execution.

### CI validation (no upstream calls)
- Add a unit smoke test that executes the Prefect flow with a stubbed local runner and asserts artifact naming.
- Add a GitHub Actions workflow that installs `--extra prefect` and runs the smoke test on PRs.

