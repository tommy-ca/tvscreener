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

    def task(*_args: Any, **_kwargs: Any):  # type: ignore[no-redef]
        def _decorator(fn):
            return fn

        return _decorator

    def flow(*_args: Any, **_kwargs: Any):  # type: ignore[no-redef]
        def _decorator(fn):
            return fn

        return _decorator

    @contextlib.contextmanager
    def tags(*_args: Any, **_kwargs: Any):  # type: ignore[no-redef]
        yield


from tvscreener_ext.runner import LocalRunner, PipelineRunSpec, RunResult


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

        from tvscreener_ext.semantic_artifacts import (
            resolve_latest_successful_data_params_hash,
            semantic_opportunity_grade_summary,
            semantic_opportunity_health,
            semantic_opportunity_top_rows,
        )

        def _to_md_table(rows: list[dict[str, Any]], limit: int = 15) -> str:
            if not rows:
                return ""

            cols = list(rows[0].keys())
            cols = cols[:12]
            header = "| " + " | ".join(cols) + " |"
            sep = "| " + " | ".join(["---"] * len(cols)) + " |"
            body = []
            for r in rows[:limit]:
                body.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
            return "\n".join([header, sep, *body])

        data_params_hash = resolve_latest_successful_data_params_hash(spec)
        rows = (
            semantic_opportunity_top_rows(data_params_hash=data_params_hash, limit=30)
            if data_params_hash
            else None
        )
        summary = (
            semantic_opportunity_grade_summary(data_params_hash=data_params_hash, limit=50)
            if data_params_hash
            else None
        )

        key = _prefect_matrix_key(spec)
        blocks: list[str] = [
            f"**analytics params_hash**: `{params_hash}`",
        ]
        if data_params_hash:
            blocks.append(f"**data params_hash**: `{data_params_hash}`")
        blocks += [
            "",
            "## Matrix",
            "```text",
            matrix_text.rstrip(),
            "```",
        ]

        if rows:
            blocks += [
                "",
                "## Top Rows",
                _to_md_table(rows, limit=15),
            ]

        if data_params_hash:
            health = semantic_opportunity_health(data_params_hash=data_params_hash)
            if health:
                blocks += [
                    "",
                    "## Health",
                    "```json",
                    json.dumps(health, indent=2, sort_keys=True, default=str),
                    "```",
                ]

        if (os.getenv("TVSCREENER_PUBLISH_RESULTS_SUMMARY") or "").strip() == "1" and summary:
            blocks += [
                "",
                "## Grade Summary",
                _to_md_table(summary, limit=25),
            ]

        create_markdown_artifact(
            key=key,
            markdown="\n".join([b for b in blocks if b is not None]),
            description="Matrix + decision context (single artifact)",
        )


def _prefect_results_key(spec: PipelineRunSpec) -> str:
    return _prefect_matrix_key(spec).replace("-matrix-", "-results-", 1)


def _maybe_publish_prefect_results_table_artifact(
    *, spec: PipelineRunSpec, params_hash: str, results_path: str | None
) -> None:
    # Prefer one artifact per run-spec total; keep table artifacts opt-in.
    if (os.getenv("TVSCREENER_PUBLISH_TABLE_ARTIFACTS") or "").strip() != "1":
        return
    try:
        from prefect.artifacts import create_table_artifact

        from tvscreener_ext.semantic_artifacts import (
            resolve_latest_successful_data_params_hash,
            semantic_opportunity_grade_summary,
            semantic_opportunity_top_rows,
        )

        data_params_hash = resolve_latest_successful_data_params_hash(spec) or ""

        semantic_rows = (
            semantic_opportunity_top_rows(data_params_hash=data_params_hash, limit=30)
            if data_params_hash
            else None
        )
        rows = semantic_rows

        if rows is None and results_path:
            import pandas as pd

            def _coerce_cell(value: Any) -> Any:
                if pd.isna(value):
                    return None
                if hasattr(value, "item"):
                    try:
                        return value.item()
                    except Exception:
                        return value
                return value

            df = pd.read_parquet(results_path)
            subset = df.head(30)
            rows = []
            for _, row in subset.iterrows():
                rows.append({col: _coerce_cell(row[col]) for col in subset.columns})

        if not rows:
            return

        desc = (
            f"Top rows from data `{data_params_hash}` (analytics `{params_hash}`)"
            if semantic_rows is not None
            else f"Top rows from `{params_hash}`"
        )
        create_table_artifact(
            key=_prefect_results_key(spec),
            table=rows,
            description=desc,
        )

        # Keep artifact volume down by default.
        if (os.getenv("TVSCREENER_PUBLISH_RESULTS_SUMMARY") or "").strip() == "1":
            summary = (
                semantic_opportunity_grade_summary(data_params_hash=data_params_hash, limit=50)
                if data_params_hash
                else None
            )
            if summary:
                create_table_artifact(
                    key=f"{_prefect_results_key(spec)}-summary",
                    table=summary,
                    description=f"Grade/direction summary for `{data_params_hash}`",
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
    prev_semantic = os.environ.get("TVSCREENER_SEMANTIC_RUNTIME")
    os.environ["TVSCREENER_RUN_DIR"] = run_dir
    os.environ["TVSCREENER_STRICT_PERSIST"] = "1"
    # Do not force a semantic runtime; default is auto (Sidemantic if installed).
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

        if prev_semantic is None:
            os.environ.pop("TVSCREENER_SEMANTIC_RUNTIME", None)
        else:
            os.environ["TVSCREENER_SEMANTIC_RUNTIME"] = prev_semantic
    matrix_text = console.export_text() if console is not None else None
    return res, matrix_text


@flow(name="tvscreener-run", flow_run_name="tvscreener-batch-{batch_path}")  # type: ignore[misc]
def prefect_run_flow(
    batch_path: str,
    artifacts_dir: str = "artifacts/runs",
    data_concurrency: int = 1,
    analytics_concurrency: int = 8,
    rate_limit: dict[str, Any] | None = None,
    skip_existing: bool = False,
) -> dict:
    """Batch entrypoint for Prefect deployments."""
    from tvscreener_ext.orchestrator import ScreenerController

    controller = ScreenerController(console=None)

    # Load batch from JSON
    full_batch_path = Path(batch_path)
    if not full_batch_path.is_absolute():
        # Search relative to package or CWD
        import tvscreener_ext.prefect

        pkg_root = Path(tvscreener_ext.prefect.__file__).parent
        if (pkg_root / "batches" / full_batch_path.name).exists():
            full_batch_path = pkg_root / "batches" / full_batch_path.name

    with open(full_batch_path) as f:
        specs_raw = json.load(f)

    if isinstance(specs_raw, dict):
        specs_raw = [specs_raw]

    results = []
    for raw in specs_raw:
        spec = PipelineRunSpec.model_validate(raw).normalized()
        params_hash = spec.params_hash or "unknown"

        base_dir = _resolve_base_dir(artifacts_dir)
        run_dir = base_dir / params_hash
        _ensure_dir(run_dir)

        # Resolve universe/pairs for determinism
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

        # Execute stages
        data_res: RunResult | None = None
        analytics_res: RunResult | None = None
        data_matrix: str | None = None
        analytics_matrix: str | None = None

        if spec.pipeline_mode in ("data", "both"):
            data_res, data_matrix = _run_data_task(spec, str(run_dir))

        if spec.pipeline_mode in ("analytics", "both"):
            analytics_res, analytics_matrix = _run_analytics_task(spec, str(run_dir))

        # Artifacts
        matrix_text = analytics_matrix or data_matrix
        if matrix_text:
            _write_matrix_artifact(run_dir, matrix_text)
            _maybe_publish_prefect_matrix_artifact(
                spec=spec, params_hash=params_hash, matrix_text=matrix_text
            )

        if analytics_output:
            _maybe_publish_prefect_results_table_artifact(
                spec=spec, params_hash=params_hash, results_path=analytics_output
            )

        payload = {
            "params_hash": params_hash,
            "success": bool(
                (data_res.success if data_res else True)
                and (analytics_res.success if analytics_res else True)
            ),
        }
        _write_json(run_dir / "run_result.json", payload)
        results.append(payload)

    return {"results": results}
