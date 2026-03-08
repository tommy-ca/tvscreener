from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

try:
    from prefect import flow, tags, task

    _PREFECT_AVAILABLE = True
except Exception:  # pragma: no cover
    # Prefect is an optional dependency; import lazily at runtime.
    _PREFECT_AVAILABLE = False
    flow = None  # type: ignore[assignment]
    tags = None  # type: ignore[assignment]
    task = None  # type: ignore[assignment]

from tvscreener.lib.pipeline_runner import LocalRunner, PipelineRunSpec, RunResult


def _console_for_spec(spec: PipelineRunSpec):
    if not bool(spec.matrix):
        return None

    # Record console output so matrix rendering can be persisted as an artifact
    # and mirrored into Prefect logs.
    from rich.console import Console

    return Console(record=True)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _default_results_path(run_dir: Path, spec: PipelineRunSpec) -> Path:
    return run_dir / f"{spec.scanner_family}_results.parquet"


def _write_json(path: Path, payload: object) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _write_matrix_artifact(run_dir: Path, matrix_text: str) -> None:
    # Keep it ASCII-friendly and stable for diffs.
    (run_dir / "matrix.txt").write_text(matrix_text, encoding="utf-8")


def _resolve_base_dir(artifacts_dir: str) -> Path:
    base_dir = Path(artifacts_dir)
    if base_dir.is_absolute():
        return base_dir
    return Path.cwd() / base_dir


def _prefect_required() -> None:
    if not _PREFECT_AVAILABLE:
        raise RuntimeError(
            "Prefect runner requires optional dependency. Install with: uv sync --extra prefect"
        )


def run_prefect(spec: PipelineRunSpec, *, artifacts_dir: str = "artifacts/runs") -> dict:
    """Execute a PipelineRunSpec via Prefect in-process.

    This is the seamless entrypoint used by `tvscreener-scan --runner prefect`.
    """
    _prefect_required()
    spec = spec.normalized()
    params_hash: str = spec.params_hash or spec.compute_params_hash()
    prefect_flow = cast(Any, prefect_run_flow)
    return prefect_flow(
        spec_payload=spec.model_dump(),
        params_hash=params_hash,
        artifacts_dir=artifacts_dir,
    )


@task(retries=2, retry_delay_seconds=10)  # type: ignore[misc]
def _run_data_task(spec: PipelineRunSpec) -> tuple[RunResult, str | None]:
    data_spec = spec.model_copy(update={"pipeline_mode": "data"}).normalized()
    console = _console_for_spec(data_spec)
    res = LocalRunner(console=console).run(data_spec)
    matrix_text = console.export_text() if console is not None else None
    return res, matrix_text


@task(retries=0)  # type: ignore[misc]
def _run_analytics_task(spec: PipelineRunSpec) -> tuple[RunResult, str | None]:
    analytics_spec = spec.model_copy(update={"pipeline_mode": "analytics"}).normalized()
    console = _console_for_spec(analytics_spec)
    res = LocalRunner(console=console).run(analytics_spec)
    matrix_text = console.export_text() if console is not None else None
    return res, matrix_text


@flow(name="tvscreener-run", flow_run_name="tvscreener-{params_hash}")  # type: ignore[misc]
def prefect_run_flow(
    spec_payload: dict[str, Any], params_hash: str, artifacts_dir: str = "artifacts/runs"
) -> dict:
    spec = PipelineRunSpec.model_validate(spec_payload).normalized()

    base_dir = _resolve_base_dir(artifacts_dir)
    run_dir = base_dir / params_hash
    _ensure_dir(run_dir)

    analytics_output = spec.output
    if spec.pipeline_mode in ("analytics", "both") and not analytics_output:
        analytics_output = str(_default_results_path(run_dir, spec))
        spec = spec.model_copy(update={"output": analytics_output}).normalized()
    _write_json(run_dir / "run_spec.json", spec.model_dump())

    with tags(  # type: ignore[misc]
        f"params_hash:{params_hash}",
        f"scanner:{spec.scanner_family}",
        f"pipeline:{spec.pipeline_mode}",
        f"asset_type:{spec.asset_type}",
    ):
        if spec.pipeline_mode == "data":
            res, matrix_text = _run_data_task(spec)
            matrix_path = None
            if matrix_text:
                _write_matrix_artifact(run_dir, matrix_text)
                matrix_path = str(run_dir / "matrix.txt")
            payload = {
                "spec_version": spec.spec_version,
                "params_hash": params_hash,
                "scanner_family": spec.scanner_family,
                "pipeline_mode_requested": spec.pipeline_mode,
                "pipeline_mode_executed": "data",
                "artifacts_dir": str(run_dir),
                "run_spec_path": str(run_dir / "run_spec.json"),
                "run_result_path": str(run_dir / "run_result.json"),
                "matrix_path": matrix_path,
                "data": res.model_dump(),
                "success": bool(res.success),
            }
            _write_json(run_dir / "run_result.json", payload)
            return payload

        if spec.pipeline_mode == "analytics":
            res, matrix_text = _run_analytics_task(spec)
            matrix_path = None
            if matrix_text:
                _write_matrix_artifact(run_dir, matrix_text)
                matrix_path = str(run_dir / "matrix.txt")
            payload = {
                "spec_version": spec.spec_version,
                "params_hash": params_hash,
                "scanner_family": spec.scanner_family,
                "pipeline_mode_requested": spec.pipeline_mode,
                "pipeline_mode_executed": "analytics",
                "artifacts_dir": str(run_dir),
                "run_spec_path": str(run_dir / "run_spec.json"),
                "run_result_path": str(run_dir / "run_result.json"),
                "results_path": analytics_output,
                "matrix_path": matrix_path,
                "analytics": {**res.model_dump(), "results_path": analytics_output},
                "success": bool(res.success),
            }
            _write_json(run_dir / "run_result.json", payload)
            return payload

        data_res, data_matrix_text = _run_data_task(spec)
        analytics_res, analytics_matrix_text = _run_analytics_task(spec)

        matrix_path = None
        matrix_text = analytics_matrix_text or data_matrix_text
        if matrix_text:
            _write_matrix_artifact(run_dir, matrix_text)
            matrix_path = str(run_dir / "matrix.txt")

        payload = {
            "spec_version": spec.spec_version,
            "params_hash": spec.params_hash,
            "scanner_family": spec.scanner_family,
            "pipeline_mode_requested": spec.pipeline_mode,
            "pipeline_mode_executed": "both",
            "artifacts_dir": str(run_dir),
            "run_spec_path": str(run_dir / "run_spec.json"),
            "run_result_path": str(run_dir / "run_result.json"),
            "results_path": analytics_output,
            "matrix_path": matrix_path,
            "data": data_res.model_dump(),
            "analytics": {**analytics_res.model_dump(), "results_path": analytics_output},
            "success": bool(data_res.success and analytics_res.success),
        }
        _write_json(run_dir / "run_result.json", payload)
        return payload
