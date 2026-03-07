from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from pathlib import Path

import pytest


def test_prefect_flow_writes_expected_artifacts(tmp_path, monkeypatch):
    pytest.importorskip("prefect")

    from tvscreener.lib import prefect_runner as pr
    from tvscreener.lib.pipeline_runner import PipelineRunSpec, RunResult

    monkeypatch.setenv("PREFECT_LOGGING_LEVEL", "ERROR")
    monkeypatch.setenv("PREFECT_LOGGING_INTERNAL_LEVEL", "ERROR")

    class DummyRunner:
        def __init__(self, console=None):
            self._console = console

        def run(self, spec: PipelineRunSpec) -> RunResult:
            # Simulate the analytics stage producing the default parquet artifact.
            if spec.pipeline_mode == "analytics" and spec.output:
                out = Path(spec.output)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"")

            now = datetime.now(tz=UTC)
            return RunResult(
                params_hash=spec.params_hash or spec.compute_params_hash(),
                scanner_family=spec.scanner_family,
                pipeline_mode_executed=spec.pipeline_mode,
                started_at_utc=now,
                finished_at_utc=now,
                success=True,
                result_count=1,
                exit_code=0,
                errors=[],
            )

    monkeypatch.setattr(pr, "LocalRunner", DummyRunner)
    monkeypatch.setattr(pr, "tags", lambda *_args, **_kwargs: contextlib.nullcontext())

    # Avoid Prefect orchestration entirely (no ephemeral server):
    # - replace Prefect-decorated tasks with plain functions
    def _data_fn(spec: PipelineRunSpec) -> RunResult:
        data_spec = spec.model_copy(update={"pipeline_mode": "data"}).normalized()
        return DummyRunner(console=None).run(data_spec)

    def _analytics_fn(spec: PipelineRunSpec) -> RunResult:
        analytics_spec = spec.model_copy(update={"pipeline_mode": "analytics"}).normalized()
        return DummyRunner(console=None).run(analytics_spec)

    monkeypatch.setattr(pr, "_run_data_task", _data_fn)
    monkeypatch.setattr(pr, "_run_analytics_task", _analytics_fn)

    artifacts_dir = tmp_path / "prefect-artifacts"
    spec = PipelineRunSpec(
        scanner_family="opportunity",
        pipeline_mode="both",
        asset_type="forex",
        universe="majors",
        timeframes=["15", "60", "240"],
    ).normalized()

    # Call the underlying flow function directly to avoid starting Prefect's ephemeral API server
    # (which can be sensitive to local Prefect DB/migration state in CI/dev environments).
    payload = pr.prefect_run_flow.fn(  # type: ignore[attr-defined]
        spec_payload=spec.model_dump(),
        params_hash=spec.params_hash or spec.compute_params_hash(),
        artifacts_dir=str(artifacts_dir),
    )

    run_dir = artifacts_dir / (spec.params_hash or "")
    assert (run_dir / "run_spec.json").exists()
    assert (run_dir / "run_result.json").exists()

    assert payload["success"] is True
    assert payload["pipeline_mode_executed"] == "both"
    assert payload["params_hash"] == spec.params_hash

    results_path = payload["analytics"]["results_path"]
    assert results_path.endswith("opportunity_results.parquet")
    assert Path(results_path).exists()
