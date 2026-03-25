from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Literal

from dotenv import load_dotenv

from tvscreener_ext.runner import LocalRunner, PipelineRunSpec
from tvscreener_ext.upstream import ensure_upstream_tvscreener

RunnerName = Literal["local", "prefect", "export"]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="tvscreener-ext-scan")
    p.add_argument("--runner", choices=["local", "prefect", "export"], default="local")
    p.add_argument("--scanner", dest="scanner_family", default="opportunity")
    p.add_argument(
        "--pipeline", dest="pipeline_mode", choices=["data", "analytics", "both"], default="both"
    )
    p.add_argument("--asset-type", required=True, choices=["forex", "crypto", "stock"])
    p.add_argument("--instrument-type", choices=["spot", "perp"], default=None)
    p.add_argument("--universe", required=True)
    p.add_argument("--timeframes", default="240,60,15")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--matrix", action="store_true")
    p.add_argument("--no-matrix", action="store_true")
    p.add_argument("--config", dest="config_path", default=None)
    p.add_argument("--artifacts-dir", default="artifacts/runs")
    p.add_argument("--output", default=None)
    p.add_argument("--spec-out", default=None)
    return p.parse_args(argv)


def _spec_from_args(a: argparse.Namespace) -> PipelineRunSpec:
    tfs = [t.strip() for t in str(a.timeframes).split(",") if t.strip()]
    matrix = bool(a.matrix)
    if bool(a.no_matrix):
        matrix = False

    return PipelineRunSpec(
        scanner_family=str(a.scanner_family),
        pipeline_mode=str(a.pipeline_mode),
        asset_type=str(a.asset_type),
        instrument_type=str(a.instrument_type) if a.instrument_type else None,
        universe=str(a.universe),
        timeframes=tfs,
        limit=int(a.limit),
        matrix=matrix,
        config_path=str(a.config_path) if a.config_path else None,
        artifacts_dir=str(a.artifacts_dir),
        output=str(a.output) if a.output else None,
    ).normalized()


def _export_spec(spec: PipelineRunSpec, *, spec_out: str | None) -> int:
    payload = spec.model_dump(mode="json")
    txt = json.dumps(payload, indent=2, sort_keys=True)
    if spec_out:
        from pathlib import Path

        Path(spec_out).write_text(txt + "\n", encoding="utf-8")
        return 0
    sys.stdout.write(txt + "\n")
    return 0


def _run_local(spec: PipelineRunSpec) -> int:
    res = LocalRunner().run(spec)
    return 0 if res.success else 2


def _run_prefect(spec: PipelineRunSpec) -> int:
    try:
        from prefect import flow, task
    except Exception:
        print("Prefect is not installed. Run with `--extra prefect`.")
        return 2

    timeout_seconds = int(os.getenv("TVSCREENER_PREFECT_TASK_TIMEOUT_SECONDS", "1800"))

    @task(timeout_seconds=timeout_seconds)
    def _task_run(payload: dict[str, object]) -> dict[str, object]:
        inner = PipelineRunSpec.model_validate(payload).normalized()
        res = LocalRunner().run(inner)

        if (res.matrix_md_path or res.matrix_path) and os.getenv(
            "TVSCREENER_PUBLISH_RESULTS_SUMMARY", "0"
        ).strip() == "1":
            try:
                from pathlib import Path

                from prefect.artifacts import create_markdown_artifact

                if res.matrix_md_path:
                    md = Path(res.matrix_md_path).read_text(encoding="utf-8")
                else:
                    matrix_text = Path(str(res.matrix_path)).read_text(encoding="utf-8")
                    md = f"```text\n{matrix_text.rstrip()}\n```"
                create_markdown_artifact(
                    key=f"tvscreener-matrix-{inner.params_hash}",
                    markdown=md,
                    description="Matrix (extensions)",
                )
            except Exception:
                pass

        if os.getenv("TVSCREENER_PUBLISH_TABLE_ARTIFACTS", "0").strip() == "1" and res.results_path:
            try:
                import pandas as pd
                from prefect.artifacts import create_table_artifact

                df = pd.read_parquet(str(res.results_path)).head(25)
                df = df.where(pd.notnull(df), None)
                create_table_artifact(
                    key=f"tvscreener-results-{inner.params_hash}",
                    table=df.to_dict(orient="records"),
                    description="Results preview (extensions)",
                )
            except Exception:
                pass

        return {
            "success": bool(res.success),
            "params_hash": res.params_hash,
            "result_count": int(res.result_count),
            "results_path": res.results_path,
            "matrix_path": res.matrix_path,
            "matrix_md_path": res.matrix_md_path,
            "errors": list(res.errors),
        }

    @flow(name="tvscreener-run", flow_run_name="tvscreener-{params_hash}")
    def _flow_run(payload: dict[str, object], params_hash: str) -> dict[str, object]:
        return _task_run(payload)

    payload = spec.model_dump(mode="json")
    out = _flow_run(payload, params_hash=str(spec.params_hash))
    return 0 if bool(out.get("success")) else 2


def main(argv: list[str] | None = None) -> int:
    load_dotenv(override=False)
    ensure_upstream_tvscreener()

    args = _parse_args((sys.argv if argv is None else argv)[1:])
    spec = _spec_from_args(args)

    if str(args.runner) == "export":
        return _export_spec(spec, spec_out=str(args.spec_out) if args.spec_out else None)
    if str(args.runner) == "prefect":
        return _run_prefect(spec)
    return _run_local(spec)


if __name__ == "__main__":
    raise SystemExit(main())
