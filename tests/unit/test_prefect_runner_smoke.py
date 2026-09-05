from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest


def test_prefect_flow_writes_expected_artifacts(tmp_path, monkeypatch):
    pytest.importorskip("prefect")

    from tvscreener_ext import prefect_runner as pr
    from tvscreener_ext.runner import PipelineRunSpec, RunResult

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
                params_hash=spec.params_hash or "test_hash",
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
    def _data_fn(spec: PipelineRunSpec, _run_dir: str):
        data_spec = spec.model_copy(update={"pipeline_mode": "data"}).normalized()
        return DummyRunner(console=None).run(data_spec), None

    def _analytics_fn(spec: PipelineRunSpec, _run_dir: str):
        analytics_spec = spec.model_copy(update={"pipeline_mode": "analytics"}).normalized()
        return DummyRunner(console=None).run(analytics_spec), None

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

    # Create dummy batch file
    batch_file = tmp_path / "test_batch.json"
    batch_file.write_text(json.dumps([spec.model_dump(mode="json")]))
    # Call the underlying flow function directly
    res = pr.prefect_run_flow.fn(  # type: ignore[attr-defined]
        batch_path=str(batch_file),
        artifacts_dir=str(artifacts_dir),
    )

    payload = res["results"][0]
    run_dir = artifacts_dir / (spec.params_hash or "")
    assert (run_dir / "run_spec.json").exists()
    assert (run_dir / "run_result.json").exists()

    assert payload["success"] is True
    assert payload["params_hash"] == spec.params_hash
