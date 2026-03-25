from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

from prefect import task

from tvscreener_ext.runner import LocalRunner, PipelineRunSpec


def _sanitize_key_part(part: str) -> str:
    keep = []
    for ch in (part or "").strip().lower():
        if ch.isalnum() or ch == "-":
            keep.append(ch)
        else:
            keep.append("-")
    out = "".join(keep)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def matrix_artifact_key(spec: PipelineRunSpec) -> str:
    parts = [
        "tvscreener",
        "matrix",
        _sanitize_key_part(spec.scanner_family) or "unknown",
        _sanitize_key_part(spec.asset_type) or "unknown",
    ]
    if spec.instrument_type:
        parts.append(_sanitize_key_part(spec.instrument_type))
    parts.append(_sanitize_key_part(spec.universe) or "unknown")
    return "-".join([p for p in parts if p])


def results_artifact_key(spec: PipelineRunSpec) -> str:
    base = matrix_artifact_key(spec)
    return base.replace("-matrix-", "-results-")


def results_summary_artifact_key(spec: PipelineRunSpec) -> str:
    return f"{results_artifact_key(spec)}-summary"


def _table_from_json(path: str, *, limit: int = 50) -> list[dict[str, Any]]:
    import json

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    rows = [r for r in raw if isinstance(r, dict)]
    if limit:
        rows = rows[: int(limit)]
    return cast(list[dict[str, Any]], rows)


@task(timeout_seconds=int(os.getenv("TVSCREENER_PREFECT_TASK_TIMEOUT_SECONDS", "1800")))
def run_data_stage(spec_payload: dict[str, Any]) -> dict[str, Any]:
    spec = PipelineRunSpec.model_validate(spec_payload).normalized()
    spec = spec.model_copy(update={"pipeline_mode": "data", "matrix": False})
    res = LocalRunner().run(spec)
    return {
        "params_hash": res.params_hash,
        "success": bool(res.success),
        "result_count": int(res.result_count),
        "errors": list(res.errors),
        "pipeline_mode_executed": res.pipeline_mode_executed,
    }


@task(timeout_seconds=int(os.getenv("TVSCREENER_PREFECT_TASK_TIMEOUT_SECONDS", "1800")))
def run_analytics_stage(spec_payload: dict[str, Any]) -> dict[str, Any]:
    spec = PipelineRunSpec.model_validate(spec_payload).normalized()
    spec = spec.model_copy(update={"pipeline_mode": "analytics"})
    res = LocalRunner().run(spec)

    if res.matrix_md_path or res.matrix_path:
        try:
            from prefect.artifacts import create_markdown_artifact

            if res.matrix_md_path:
                md = Path(res.matrix_md_path).read_text(encoding="utf-8")
            else:
                matrix_text = Path(str(res.matrix_path)).read_text(encoding="utf-8")
                md = f"```text\n{matrix_text.rstrip()}\n```"
            create_markdown_artifact(
                key=matrix_artifact_key(spec),
                markdown=md,
                description="Matrix (extensions)",
            )
        except Exception as exc:
            if os.getenv("TVSCREENER_PREFECT_ARTIFACT_DEBUG", "0").strip() == "1":
                print(f"prefect_table_artifact_error err={exc}")

    if os.getenv("TVSCREENER_PUBLISH_TABLE_ARTIFACTS", "1").strip() == "1":
        try:
            from prefect.artifacts import create_table_artifact

            if res.results_table_path:
                table = _table_from_json(str(res.results_table_path), limit=25)
                if table:
                    create_table_artifact(
                        key=results_artifact_key(spec),
                        table=table,
                        description="Results preview (DuckDB semantic)",
                    )

            if res.grade_summary_table_path:
                summary = _table_from_json(str(res.grade_summary_table_path), limit=50)
                if summary:
                    create_table_artifact(
                        key=results_summary_artifact_key(spec),
                        table=summary,
                        description="Grade summary (DuckDB semantic)",
                    )
        except Exception as exc:
            if os.getenv("TVSCREENER_PREFECT_ARTIFACT_DEBUG", "0").strip() == "1":
                print(f"prefect_table_artifact_error err={exc}")

    return {
        "params_hash": res.params_hash,
        "success": bool(res.success),
        "result_count": int(res.result_count),
        "results_path": res.results_path,
        "matrix_path": res.matrix_path,
        "matrix_md_path": res.matrix_md_path,
        "errors": list(res.errors),
        "pipeline_mode_executed": res.pipeline_mode_executed,
    }


@task(timeout_seconds=int(os.getenv("TVSCREENER_PREFECT_TASK_TIMEOUT_SECONDS", "1800")))
def run_both_stage(spec_payload: dict[str, Any]) -> dict[str, Any]:
    spec = PipelineRunSpec.model_validate(spec_payload).normalized()
    spec = spec.model_copy(update={"pipeline_mode": "both"})
    res = LocalRunner().run(spec)

    # Publish artifacts using the same policy as analytics.
    if res.matrix_md_path or res.matrix_path:
        try:
            from prefect.artifacts import create_markdown_artifact

            if res.matrix_md_path:
                md = Path(res.matrix_md_path).read_text(encoding="utf-8")
            else:
                matrix_text = Path(str(res.matrix_path)).read_text(encoding="utf-8")
                md = f"```text\n{matrix_text.rstrip()}\n```"
            create_markdown_artifact(
                key=matrix_artifact_key(spec),
                markdown=md,
                description="Matrix (extensions)",
            )
        except Exception:
            pass

    if os.getenv("TVSCREENER_PUBLISH_TABLE_ARTIFACTS", "1").strip() == "1":
        try:
            from prefect.artifacts import create_table_artifact

            if res.results_table_path:
                table = _table_from_json(str(res.results_table_path), limit=25)
                if table:
                    create_table_artifact(
                        key=results_artifact_key(spec),
                        table=table,
                        description="Results preview (DuckDB semantic)",
                    )

            if res.grade_summary_table_path:
                summary = _table_from_json(str(res.grade_summary_table_path), limit=50)
                if summary:
                    create_table_artifact(
                        key=results_summary_artifact_key(spec),
                        table=summary,
                        description="Grade summary (DuckDB semantic)",
                    )
        except Exception:
            pass

    return {
        "params_hash": res.params_hash,
        "success": bool(res.success),
        "result_count": int(res.result_count),
        "results_path": res.results_path,
        "matrix_path": res.matrix_path,
        "matrix_md_path": res.matrix_md_path,
        "errors": list(res.errors),
        "pipeline_mode_executed": res.pipeline_mode_executed,
    }
