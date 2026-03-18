from __future__ import annotations

import contextlib
import json
import os
import re
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

    # Use a generous width so saved `matrix.txt` artifacts don't truncate
    # emoji grids into "…" on narrow default consoles.
    return Console(record=True, width=140, force_terminal=True)


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


def _prefect_matrix_key(spec: PipelineRunSpec) -> str:
    def _sanitize(part: str) -> str:
        cleaned = re.sub(r"[^a-z0-9-]+", "-", part.strip().lower())
        cleaned = re.sub(r"-+", "-", cleaned).strip("-")
        return cleaned

    parts: list[str] = [
        "tvscreener",
        "matrix",
        _sanitize(str(spec.scanner_family or "")) or "unknown",
        _sanitize(str(spec.asset_type or "")) or "unknown",
    ]
    if spec.instrument_type:
        parts.append(_sanitize(str(spec.instrument_type)))
    if spec.universe:
        parts.append(_sanitize(str(spec.universe)))
    if spec.timeframe_set_id:
        parts.append(_sanitize(str(spec.timeframe_set_id)))
    return "-".join([p for p in parts if p])


def _maybe_publish_prefect_matrix_artifact(
    *, spec: PipelineRunSpec, params_hash: str, matrix_text: str
) -> None:
    if not matrix_text.strip():
        return

    with contextlib.suppress(Exception):
        from prefect.artifacts import create_markdown_artifact

        key = _prefect_matrix_key(spec)
        markdown = "\n".join(
            [
                f"**params_hash**: `{params_hash}`",
                "",
                "```text",
                matrix_text.rstrip(),
                "```",
            ]
        )
        create_markdown_artifact(
            key=key,
            markdown=markdown,
            description="Latest matrix view (versioned by key)",
        )


def _prefect_results_key(spec: PipelineRunSpec) -> str:
    return _prefect_matrix_key(spec).replace("-matrix-", "-results-", 1)


def _maybe_publish_prefect_results_table_artifact(
    *, spec: PipelineRunSpec, params_hash: str, results_path: str | None
) -> None:
    if not results_path:
        return

    try:
        import pandas as pd
        from prefect.artifacts import create_table_artifact

        def _coerce_cell(value: Any) -> Any:
            if pd.isna(value):
                return None
            # Numpy scalars
            if hasattr(value, "item"):
                try:
                    return value.item()
                except Exception:
                    pass
            return value

        df = pd.read_parquet(results_path)
        preferred_cols = [
            "PAIR",
            "Name",
            "Price",
            "RVOL",
            "Volume",
            "ENSEMBLE_SCORE",
            "GRADE",
            "DIRECTION",
            "GRID_ALIGNED",
            "GRID_TOTAL",
            "CONFLUENCE_LEVEL",
            "TOTAL_CONFLUENCE",
            "TF_CONFLUENCE",
            "TREND_SCORE",
            "MA_SCORE",
            "OSC_SCORE",
            "ROC_SCORE",
            "ROC_AVG",
            "TREND_DIR",
            "MA_DIR",
            "OSC_DIR",
            "ROC_DIR",
            "RATING_SCORE",
        ]
        cols = [c for c in preferred_cols if c in df.columns]
        if not cols:
            return

        subset = df[cols].head(30)
        rows: list[dict[str, Any]] = []
        for _, row in subset.iterrows():
            rows.append({col: _coerce_cell(row[col]) for col in subset.columns})
        create_table_artifact(
            key=_prefect_results_key(spec),
            table=rows,
            description=f"Top rows from `{params_hash}`",
        )
    except Exception:
        return


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
def _run_data_task(spec: PipelineRunSpec, run_dir: str) -> tuple[RunResult, str | None]:
    data_spec = spec.model_copy(update={"pipeline_mode": "data"}).normalized()
    console = _console_for_spec(data_spec)
    previous = os.environ.get("TVSCREENER_RUN_DIR")
    prev_strict = os.environ.get("TVSCREENER_STRICT_PERSIST")
    os.environ["TVSCREENER_RUN_DIR"] = run_dir
    os.environ["TVSCREENER_STRICT_PERSIST"] = "1"
    try:
        res = LocalRunner(console=console).run(data_spec)
    finally:
        if previous is None:
            os.environ.pop("TVSCREENER_RUN_DIR", None)
        else:
            os.environ["TVSCREENER_RUN_DIR"] = previous

        if prev_strict is None:
            os.environ.pop("TVSCREENER_STRICT_PERSIST", None)
        else:
            os.environ["TVSCREENER_STRICT_PERSIST"] = prev_strict
    matrix_text = console.export_text() if console is not None else None
    return res, matrix_text


@task(retries=2, retry_delay_seconds=10)  # type: ignore[misc]
def _run_analytics_task(spec: PipelineRunSpec, run_dir: str) -> tuple[RunResult, str | None]:
    analytics_spec = spec.model_copy(update={"pipeline_mode": "analytics"}).normalized()
    console = _console_for_spec(analytics_spec)
    previous = os.environ.get("TVSCREENER_RUN_DIR")
    prev_strict = os.environ.get("TVSCREENER_STRICT_PERSIST")
    os.environ["TVSCREENER_RUN_DIR"] = run_dir
    os.environ["TVSCREENER_STRICT_PERSIST"] = "1"
    try:
        res = LocalRunner(console=console).run(analytics_spec)
    finally:
        if previous is None:
            os.environ.pop("TVSCREENER_RUN_DIR", None)
        else:
            os.environ["TVSCREENER_RUN_DIR"] = previous

        if prev_strict is None:
            os.environ.pop("TVSCREENER_STRICT_PERSIST", None)
        else:
            os.environ["TVSCREENER_STRICT_PERSIST"] = prev_strict
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

    # Resolve universe/pairs once for determinism and persist universe.json
    # into the run artifacts directory when applicable.
    controller = None
    with contextlib.suppress(Exception):
        from tvscreener.lib.orchestrator import ScreenerController

        controller = ScreenerController(console=None)

    if controller is not None:
        previous = os.environ.get("TVSCREENER_RUN_DIR")
        os.environ["TVSCREENER_RUN_DIR"] = str(run_dir)
        try:
            req = controller.resolve_defaults(spec.to_scan_request())
            pairs = controller.get_pairs(
                req.assets.asset_type,
                req.assets.universe,
                req.assets.pairs,
                instrument_type=getattr(req.assets, "instrument_type", None),
            )
            spec = spec.model_copy(
                update={"pairs": pairs, "universe": req.assets.universe}
            ).normalized()
        finally:
            if previous is None:
                os.environ.pop("TVSCREENER_RUN_DIR", None)
            else:
                os.environ["TVSCREENER_RUN_DIR"] = previous

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
            res, matrix_text = _run_data_task(spec, str(run_dir))
            matrix_path = None
            if matrix_text:
                _write_matrix_artifact(run_dir, matrix_text)
                _maybe_publish_prefect_matrix_artifact(
                    spec=spec, params_hash=params_hash, matrix_text=matrix_text
                )
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
            res, matrix_text = _run_analytics_task(spec, str(run_dir))
            matrix_path = None
            if matrix_text:
                _write_matrix_artifact(run_dir, matrix_text)
                _maybe_publish_prefect_matrix_artifact(
                    spec=spec, params_hash=params_hash, matrix_text=matrix_text
                )
                matrix_path = str(run_dir / "matrix.txt")

            _maybe_publish_prefect_results_table_artifact(
                spec=spec, params_hash=params_hash, results_path=analytics_output
            )
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

        data_res, data_matrix_text = _run_data_task(spec, str(run_dir))
        analytics_res, analytics_matrix_text = _run_analytics_task(spec, str(run_dir))

        matrix_path = None
        matrix_text = analytics_matrix_text or data_matrix_text
        if matrix_text:
            _write_matrix_artifact(run_dir, matrix_text)
            _maybe_publish_prefect_matrix_artifact(
                spec=spec, params_hash=params_hash, matrix_text=matrix_text
            )
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
