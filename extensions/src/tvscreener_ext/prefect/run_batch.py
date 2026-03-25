from __future__ import annotations

import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Any, cast

from prefect import flow
from prefect.task_runners import ConcurrentTaskRunner

from tvscreener_ext.prefect.stages import (
    run_analytics_stage,
    run_both_stage,
    run_data_stage,
)
from tvscreener_ext.runner import PipelineRunSpec


def _resolve_batch_path(batch_path: str) -> Path:
    p = Path(batch_path)
    if p.exists():
        return p

    bundled = Path(__file__).resolve().parent / "batches" / p.name
    return bundled


def _load_batch(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _rate_limit_sleep(rate_limit: dict[str, Any] | None) -> None:
    cfg = rate_limit or {}
    if not bool(cfg.get("enabled")):
        return
    base = float(cfg.get("min_interval_seconds") or 0.0)
    jitter = float(cfg.get("jitter_seconds") or 0.0)
    delay = base + (random.random() * jitter)
    if delay > 0:
        time.sleep(delay)


@flow(
    name="tvscreener-batch",
    flow_run_name="tvscreener-batch-{batch_path}",
    task_runner=ConcurrentTaskRunner(),
)
def run_batch(
    *,
    batch_path: str,
    artifacts_dir: str = "artifacts/runs",
    data_concurrency: int = 1,
    analytics_concurrency: int = 8,
    rate_limit: dict[str, Any] | None = None,
    skip_existing: bool = False,
) -> dict[str, Any]:
    batch_file = _resolve_batch_path(batch_path)
    batch = _load_batch(batch_file)
    batch_id = str(batch.get("batch_id") or batch_file.stem)

    defaults = cast(dict[str, Any], batch.get("defaults") or {})
    runs = cast(list[dict[str, Any]], batch.get("runs") or [])

    # Expand simple matrix definition if present.
    matrix = cast(dict[str, Any], batch.get("matrix") or {})
    if matrix:
        scanners = cast(list[str], matrix.get("scanners") or [])
        universes = cast(list[str], matrix.get("universes") or [])
        pipeline_mode = str(matrix.get("pipeline_mode") or defaults.get("pipeline_mode") or "data")
        for s in scanners:
            for u in universes:
                runs.append({"scanner_family": s, "universe": u, "pipeline_mode": pipeline_mode})

    sem = {
        "data": threading.Semaphore(max(1, int(data_concurrency))),
        "analytics": threading.Semaphore(max(1, int(analytics_concurrency))),
    }

    results: dict[str, Any] = {}

    for r in runs:
        spec_payload = {**defaults, **r}
        spec = PipelineRunSpec.model_validate(spec_payload).normalized()
        spec = spec.model_copy(update={"artifacts_dir": str(artifacts_dir)})

        run_dir = Path(artifacts_dir) / str(spec.params_hash)
        if skip_existing and (run_dir / "run_result.json").exists():
            results[str(spec.params_hash)] = {"skipped": True, "params_hash": str(spec.params_hash)}
            continue

        _rate_limit_sleep(rate_limit)

        if spec.pipeline_mode == "data":
            with sem["data"]:
                fut = run_data_stage.submit(spec.model_dump(mode="json"))
                results[str(spec.params_hash)] = fut
            continue

        if spec.pipeline_mode == "analytics":
            with sem["analytics"]:
                fut = run_analytics_stage.submit(spec.model_dump(mode="json"))
                results[str(spec.params_hash)] = fut
            continue

        if os.getenv("TVSCREENER_PREFECT_COMPOSE_BOTH", "0").strip() == "1":
            with sem["data"]:
                data_fut = run_data_stage.submit(spec.model_dump(mode="json"))
            with sem["analytics"]:
                analytics_fut = run_analytics_stage.submit(
                    spec.model_dump(mode="json"),
                    wait_for=data_fut,
                )
            results[str(spec.params_hash)] = {"data": data_fut, "analytics": analytics_fut}
        else:
            # Legacy behavior: a single task executes both.
            with sem["data"]:
                fut = run_both_stage.submit(spec.model_dump(mode="json"))
                results[str(spec.params_hash)] = fut

    # Resolve Prefect futures so results are deterministic and JSON-serializable.
    resolved_runs: dict[str, Any] = {}
    for params_hash, v in results.items():
        if isinstance(v, dict) and "data" in v and "analytics" in v:
            data_fut = v["data"]
            analytics_fut = v["analytics"]
            resolved_runs[params_hash] = {
                "data": data_fut.result() if hasattr(data_fut, "result") else data_fut,
                "analytics": (
                    analytics_fut.result() if hasattr(analytics_fut, "result") else analytics_fut
                ),
            }
        elif hasattr(v, "result"):
            resolved_runs[params_hash] = v.result()
        else:
            resolved_runs[params_hash] = v

    out = {"batch_id": batch_id, "results": resolved_runs}

    batch_dir = Path(artifacts_dir) / "batch" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    (batch_dir / "batch_result.json").write_text(
        json.dumps(out, indent=2, default=str),
        encoding="utf-8",
    )

    return out
