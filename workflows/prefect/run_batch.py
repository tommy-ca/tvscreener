from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
import time
from pathlib import Path
from typing import Any

from prefect import flow, tags, task
from prefect.task_runners import ConcurrentTaskRunner

from tvscreener.lib.pipeline_runner import LocalRunner, PipelineRunSpec, RunResult

_ARTIFACTS_BASE_DIR: Path | None = None


def _console_for_spec(spec: PipelineRunSpec):
    if not bool(spec.matrix):
        return None

    from rich.console import Console

    # Use a generous width so saved `matrix.txt` artifacts don't truncate
    # emoji grids into "…" on narrow default consoles.
    return Console(record=True, width=140, force_terminal=True)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _batch_id(payload: Any) -> str:
    raw = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _write_json(path: Path, payload: object) -> None:
    _ensure_dir(path.parent)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _default_results_path(run_dir: Path, spec: PipelineRunSpec) -> Path:
    return run_dir / f"{spec.scanner_family}_results.parquet"


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _chunk(seq: list[Any], size: int) -> list[list[Any]]:
    if size <= 0:
        return [seq]
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def _expand_matrix(matrix: dict[str, Any], defaults: dict[str, Any]) -> list[dict[str, Any]]:
    asset_types = matrix.get("asset_types") or [defaults.get("asset_type", "forex")]
    universes = matrix.get("universes") or [defaults.get("universe")]
    scanners = matrix.get("scanners") or [defaults.get("scanner_family", "opportunity")]
    pipeline_mode = matrix.get("pipeline_mode", defaults.get("pipeline_mode", "both"))
    timeframe_sets = matrix.get("timeframe_sets") or []

    runs: list[dict[str, Any]] = []
    for asset_type in asset_types:
        for universe in universes:
            for scanner in scanners:
                if timeframe_sets:
                    for tfs in timeframe_sets:
                        runs.append(
                            {
                                **defaults,
                                "asset_type": asset_type,
                                "universe": universe,
                                "scanner_family": scanner,
                                "pipeline_mode": pipeline_mode,
                                "timeframes": tfs,
                            }
                        )
                else:
                    runs.append(
                        {
                            **defaults,
                            "asset_type": asset_type,
                            "universe": universe,
                            "scanner_family": scanner,
                            "pipeline_mode": pipeline_mode,
                        }
                    )
    return runs


def _apply_pair_sharding(
    runs_raw: list[dict[str, Any]],
    *,
    defaults: dict[str, Any],
    sharding: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Expand runs by sharding `pairs` for each run (best-effort).

    If `pairs` is not provided for a run, we resolve pairs via `ScreenerController.get_pairs(...)` from
    `asset_type` + `universe` (or defaults) and then chunk into multiple run entries.

    This is intended for scaling: a workflow engine can fan out shards in parallel.
    """
    sharding = sharding or {}
    enabled = bool(sharding.get("enabled", False))
    max_pairs = sharding.get("max_pairs_per_run") or sharding.get("max_pairs") or None
    if not enabled and not max_pairs:
        return runs_raw, {"sharding": {"enabled": False}}
    if not max_pairs:
        # Enabled but no max specified => no-op
        return runs_raw, {"sharding": {"enabled": True, "max_pairs_per_run": None}}

    from tvscreener.lib.orchestrator import ScreenerController

    controller = ScreenerController(console=None)
    expanded: list[dict[str, Any]] = []
    stats = {
        "enabled": True,
        "max_pairs_per_run": int(max_pairs),
        "expanded_from": 0,
        "expanded_to": 0,
    }

    for r in runs_raw:
        payload = {**defaults, **(r or {})}
        if payload.get("pairs"):
            expanded.append(r)
            continue

        asset_type = payload.get("asset_type", "forex")
        universe = payload.get("universe")
        pairs = controller.get_pairs(asset_type, universe, None)
        chunks = _chunk(list(pairs), int(max_pairs))
        if len(chunks) <= 1:
            expanded.append({**r, "pairs": list(pairs)})
            continue

        stats["expanded_from"] += 1
        for c in chunks:
            expanded.append({**r, "pairs": list(c)})
        stats["expanded_to"] += len(chunks)

    return expanded, {"sharding": stats}


def load_batch_specs(batch_path: str) -> tuple[str, list[PipelineRunSpec], dict[str, Any]]:
    raw = _load_json(batch_path)
    meta: dict[str, Any] = {"batch_path": batch_path}

    if isinstance(raw, list):
        batch_id = _batch_id(raw)
        runs_raw = raw
        defaults: dict[str, Any] = {}
        sharding: dict[str, Any] | None = None
    elif isinstance(raw, dict):
        defaults = raw.get("defaults") or {}
        runs_raw: list[dict[str, Any]] = list(raw.get("runs") or [])
        if raw.get("matrix"):
            runs_raw.extend(_expand_matrix(raw["matrix"], defaults))
        sharding = raw.get("sharding") or None
        batch_id = raw.get("batch_id") or _batch_id({"defaults": defaults, "runs": runs_raw})
        meta.update({k: v for k, v in raw.items() if k not in ("runs", "matrix")})
    else:
        raise ValueError("Batch spec must be a JSON list or object")

    runs_raw, sharding_meta = _apply_pair_sharding(runs_raw, defaults=defaults, sharding=sharding)
    meta.update(sharding_meta)

    specs: list[PipelineRunSpec] = []
    for r in runs_raw:
        payload = {**defaults, **(r or {})}
        spec = PipelineRunSpec.model_validate(payload).normalized()
        specs.append(spec)

    return str(batch_id), specs, meta


class _RateLimiter:
    """A simple in-process rate limiter (per worker/process).

    This is intended to protect upstream fetch steps (TradingView) during batch fan-out.
    It is not a distributed/global limiter.
    """

    def __init__(self, min_interval_seconds: float, jitter_seconds: float = 0.0) -> None:
        self._min_interval = max(0.0, float(min_interval_seconds))
        self._jitter = max(0.0, float(jitter_seconds))
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.time()
            delay = (self._last + self._min_interval) - now
            if delay > 0:
                time.sleep(delay)
            if self._jitter > 0:
                time.sleep(random.random() * self._jitter)
            self._last = time.time()


_RATE_LIMITER: _RateLimiter | None = None


def _configure_rate_limiter(rate_limit: dict[str, Any] | None) -> None:
    global _RATE_LIMITER
    rate_limit = rate_limit or {}
    enabled = bool(rate_limit.get("enabled", False))
    if not enabled:
        _RATE_LIMITER = None
        return
    min_interval = float(rate_limit.get("min_interval_seconds", 0.0) or 0.0)
    jitter = float(rate_limit.get("jitter_seconds", 0.0) or 0.0)
    _RATE_LIMITER = _RateLimiter(min_interval_seconds=min_interval, jitter_seconds=jitter)


def _bounded_submit(
    task_fn: Any, items: list[PipelineRunSpec], *, max_in_flight: int, tag_builder: Any
) -> dict[str, Any]:
    """Submit tasks with a cap on in-flight executions (per flow run)."""
    futures: dict[str, Any] = {}
    in_flight: list[str] = []

    cap = max(1, int(max_in_flight))
    for spec in items:
        params_hash = spec.params_hash
        assert params_hash

        while len(in_flight) >= cap:
            # Block on the oldest submitted future to keep in-flight bounded.
            oldest = in_flight.pop(0)
            _ = futures[oldest].result()

        with tags(*tag_builder(spec, params_hash)):
            futures[params_hash] = task_fn.submit(spec)
            in_flight.append(params_hash)

    # Drain remaining
    for ph in list(in_flight):
        _ = futures[ph].result()

    return futures


@task(retries=2, retry_delay_seconds=10)
def run_data(spec: PipelineRunSpec) -> RunResult:
    data_spec = spec.model_copy(update={"pipeline_mode": "data"}).normalized()
    # Best-effort per-worker throttling to protect upstream fetchers.
    if _RATE_LIMITER is not None:
        _RATE_LIMITER.wait()

    run_dir = None
    if _ARTIFACTS_BASE_DIR is not None:
        run_dir = _ARTIFACTS_BASE_DIR / (data_spec.params_hash or data_spec.compute_params_hash())

    console = _console_for_spec(data_spec)

    prev_run_dir = os.environ.get("TVSCREENER_RUN_DIR")
    prev_strict = os.environ.get("TVSCREENER_STRICT_PERSIST")
    if run_dir is not None:
        os.environ["TVSCREENER_RUN_DIR"] = str(run_dir)
    os.environ["TVSCREENER_STRICT_PERSIST"] = "1"
    try:
        res = LocalRunner(console=console).run(data_spec)
    finally:
        if prev_run_dir is None:
            os.environ.pop("TVSCREENER_RUN_DIR", None)
        else:
            os.environ["TVSCREENER_RUN_DIR"] = prev_run_dir

        if prev_strict is None:
            os.environ.pop("TVSCREENER_STRICT_PERSIST", None)
        else:
            os.environ["TVSCREENER_STRICT_PERSIST"] = prev_strict

    if console is not None and _ARTIFACTS_BASE_DIR is not None:
        text = console.export_text()
        if text.strip():
            assert run_dir is not None
            _ensure_dir(run_dir)
            (run_dir / "matrix.txt").write_text(text, encoding="utf-8")
    return res


@task(retries=0)
def run_analytics(spec: PipelineRunSpec) -> RunResult:
    analytics_spec = spec.model_copy(update={"pipeline_mode": "analytics"}).normalized()

    run_dir = None
    if _ARTIFACTS_BASE_DIR is not None:
        run_dir = _ARTIFACTS_BASE_DIR / (
            analytics_spec.params_hash or analytics_spec.compute_params_hash()
        )

    console = _console_for_spec(analytics_spec)

    prev_run_dir = os.environ.get("TVSCREENER_RUN_DIR")
    if run_dir is not None:
        os.environ["TVSCREENER_RUN_DIR"] = str(run_dir)
    try:
        res = LocalRunner(console=console).run(analytics_spec)
    finally:
        if prev_run_dir is None:
            os.environ.pop("TVSCREENER_RUN_DIR", None)
        else:
            os.environ["TVSCREENER_RUN_DIR"] = prev_run_dir

    if console is not None and _ARTIFACTS_BASE_DIR is not None:
        text = console.export_text()
        if text.strip():
            assert run_dir is not None
            _ensure_dir(run_dir)
            (run_dir / "matrix.txt").write_text(text, encoding="utf-8")
    return res


@flow(name="tvscreener-batch", task_runner=ConcurrentTaskRunner())
def run_batch(
    batch_path: str,
    artifacts_dir: str = "artifacts/runs",
    *,
    data_concurrency: int | None = None,
    analytics_concurrency: int | None = None,
    rate_limit: dict[str, Any] | None = None,
    concurrency_hint: int | None = None,
    skip_existing: bool = False,
) -> dict:
    os.chdir(_repo_root())

    batch_id, specs, meta = load_batch_specs(batch_path)
    meta.setdefault("rate_limit", rate_limit or {})
    meta.setdefault("data_concurrency", data_concurrency)
    meta.setdefault("analytics_concurrency", analytics_concurrency)
    meta.setdefault("skip_existing", bool(skip_existing))

    _configure_rate_limiter(rate_limit)

    base_dir = Path(artifacts_dir)
    if not base_dir.is_absolute():
        base_dir = _repo_root() / base_dir

    global _ARTIFACTS_BASE_DIR
    _ARTIFACTS_BASE_DIR = base_dir

    batch_dir = base_dir / "batch" / batch_id
    _ensure_dir(batch_dir)
    _write_json(
        batch_dir / "batch_meta.json", {"batch_id": batch_id, "meta": meta, "count": len(specs)}
    )

    # Prepare per-run spec files and ensure analytics outputs are deterministic.
    run_specs: dict[str, PipelineRunSpec] = {}
    run_dirs: dict[str, Path] = {}
    for spec in specs:
        params_hash = spec.params_hash
        assert params_hash
        run_dir = base_dir / params_hash
        _ensure_dir(run_dir)
        run_dirs[params_hash] = run_dir

        # If analytics will run and output is missing, default to a deterministic parquet artifact path.
        if spec.pipeline_mode in ("analytics", "both") and not spec.output:
            spec = spec.model_copy(
                update={"output": str(_default_results_path(run_dir, spec))}
            ).normalized()

        run_specs[params_hash] = spec
        _write_json(run_dir / "run_spec.json", spec.model_dump())

    results: dict[str, Any] = {}
    skipped: dict[str, dict[str, bool]] = {}

    def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _maybe_synthesize_run_result(
        params_hash: str, spec: PipelineRunSpec, run_dir: Path
    ) -> bool:
        """Back-compat: synthesize run_result.json from legacy stage JSONs."""
        run_result_path = run_dir / "run_result.json"
        if run_result_path.exists():
            return True

        data_payload = _read_json_if_exists(run_dir / "run_result_data.json")
        analytics_payload = _read_json_if_exists(run_dir / "run_result_analytics.json")
        if not (data_payload or analytics_payload):
            return False

        payload: dict[str, Any] = {
            "spec_version": spec.spec_version,
            "params_hash": params_hash,
            "scanner_family": spec.scanner_family,
            "pipeline_mode_requested": spec.pipeline_mode,
            "pipeline_mode_executed": spec.pipeline_mode,
            "artifacts_dir": str(run_dir),
        }
        if data_payload is not None:
            payload["data"] = {k: v for k, v in data_payload.items() if k != "artifacts_dir"}
        if analytics_payload is not None:
            payload["analytics"] = {
                k: v for k, v in analytics_payload.items() if k != "artifacts_dir"
            }
        if spec.pipeline_mode == "both" and data_payload and analytics_payload:
            payload["pipeline_mode_executed"] = "both"

        payload["success"] = bool(
            payload.get("data", {}).get("success", True)
            and payload.get("analytics", {}).get("success", True)
        )
        _write_json(run_result_path, payload)
        return True

    def _data_tags(spec: PipelineRunSpec, params_hash: str) -> list[str]:
        return [
            f"batch:{batch_id}",
            f"params_hash:{params_hash}",
            f"scanner:{spec.scanner_family}",
            "pipeline:data",
            f"asset_type:{spec.asset_type}",
        ]

    def _analytics_tags(spec: PipelineRunSpec, params_hash: str) -> list[str]:
        return [
            f"batch:{batch_id}",
            f"params_hash:{params_hash}",
            f"scanner:{spec.scanner_family}",
            "pipeline:analytics",
            f"asset_type:{spec.asset_type}",
        ]

    data_specs: list[PipelineRunSpec] = []
    analytics_specs: list[PipelineRunSpec] = []

    for params_hash, spec in run_specs.items():
        run_dir = run_dirs[params_hash]
        stage_skipped = {"data": False, "analytics": False, "both": False}

        if skip_existing:
            # New contract: a single run_result.json is sufficient for idempotent skip.
            if (run_dir / "run_result.json").exists():
                stage_skipped["both"] = True
                stage_skipped["data"] = True
                stage_skipped["analytics"] = True
            else:
                if spec.pipeline_mode == "data":
                    if (run_dir / "run_result_data.json").exists():
                        stage_skipped["data"] = True
                elif spec.pipeline_mode == "analytics":
                    if (run_dir / "run_result_analytics.json").exists():
                        stage_skipped["analytics"] = True
                elif spec.pipeline_mode == "both":
                    # Back-compat: allow skipping "both" when legacy stage artifacts exist.
                    if _maybe_synthesize_run_result(params_hash, spec, run_dir):
                        stage_skipped["both"] = True
                        stage_skipped["data"] = True
                        stage_skipped["analytics"] = True
                    else:
                        if (run_dir / "run_result_data.json").exists():
                            stage_skipped["data"] = True
                        if (run_dir / "run_result_analytics.json").exists():
                            stage_skipped["analytics"] = True

        if stage_skipped["data"] or stage_skipped["analytics"] or stage_skipped["both"]:
            skipped[params_hash] = stage_skipped

        if spec.pipeline_mode in ("data", "both") and not stage_skipped["data"]:
            data_specs.append(spec)
        if spec.pipeline_mode in ("analytics", "both") and not stage_skipped["analytics"]:
            analytics_specs.append(spec)

    # Default to overall concurrency hint if not provided.
    if data_concurrency is None:
        data_concurrency = concurrency_hint or 1
    if analytics_concurrency is None:
        analytics_concurrency = concurrency_hint or max(1, int(data_concurrency))

    # Run data tasks (fan-out) with bounded in-flight submissions.
    data_futures = (
        _bounded_submit(
            run_data, data_specs, max_in_flight=int(data_concurrency), tag_builder=_data_tags
        )
        if data_specs
        else {}
    )

    # Run analytics tasks (fan-out; depend on data where needed).
    # Ensure all data runs complete before analytics begins for "both".
    for _params_hash, fut in data_futures.items():
        _ = fut.result()

    analytics_futures = (
        _bounded_submit(
            run_analytics,
            analytics_specs,
            max_in_flight=int(analytics_concurrency),
            tag_builder=_analytics_tags,
        )
        if analytics_specs
        else {}
    )

    # Collect and write per-run results.
    for params_hash, spec in run_specs.items():
        run_dir = run_dirs[params_hash]
        payload: dict[str, Any] = {
            "spec_version": spec.spec_version,
            "params_hash": params_hash,
            "scanner_family": spec.scanner_family,
            "pipeline_mode_requested": spec.pipeline_mode,
            "pipeline_mode_executed": spec.pipeline_mode,
            "artifacts_dir": str(run_dir),
            "run_spec_path": str(run_dir / "run_spec.json"),
            "run_result_path": str(run_dir / "run_result.json"),
        }
        if params_hash in skipped:
            payload["skipped"] = skipped[params_hash]
        if params_hash in data_futures:
            data_res = data_futures[params_hash].result()
            payload["data"] = data_res.model_dump()
        elif skip_existing and spec.pipeline_mode in ("data", "both"):
            data_payload = _read_json_if_exists(run_dir / "run_result_data.json")
            if data_payload is not None:
                payload["data"] = {k: v for k, v in data_payload.items() if k != "artifacts_dir"}
        if params_hash in analytics_futures:
            analytics_res = analytics_futures[params_hash].result()
            payload["analytics"] = {
                **analytics_res.model_dump(),
                "results_path": spec.output,
            }
            payload["results_path"] = spec.output
        elif skip_existing and spec.pipeline_mode in ("analytics", "both"):
            analytics_payload = _read_json_if_exists(run_dir / "run_result_analytics.json")
            if analytics_payload is not None:
                payload["analytics"] = {
                    k: v for k, v in analytics_payload.items() if k != "artifacts_dir"
                }
                payload["results_path"] = payload["analytics"].get("results_path")
        if spec.pipeline_mode == "both":
            payload["success"] = bool(
                payload.get("data", {}).get("success", True)
                and payload.get("analytics", {}).get("success", True)
            )

        if spec.pipeline_mode != "both":
            payload["success"] = bool(payload.get("data", {}).get("success", True))
            if "analytics" in payload:
                payload["success"] = bool(
                    payload["success"] and payload["analytics"].get("success", True)
                )

        matrix_path = run_dir / "matrix.txt"
        if matrix_path.exists():
            payload["matrix_path"] = str(matrix_path)

        _write_json(run_dir / "run_result.json", payload)
        results[params_hash] = payload

    summary = {
        "batch_id": batch_id,
        "count": len(run_specs),
        "results": results,
        "concurrency_hint": concurrency_hint,
        "batch_artifacts_dir": str(batch_dir),
    }
    _write_json(batch_dir / "batch_result.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a batch of tvscreener PipelineRunSpecs via Prefect"
    )
    parser.add_argument(
        "--batch", required=True, help="Path to batch JSON (list or object with runs/matrix)"
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts/runs",
        help="Directory to write artifacts under (relative to repo root recommended)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Max concurrent tasks for this batch run (best-effort)",
    )
    parser.add_argument(
        "--data-concurrency",
        type=int,
        default=None,
        help="Max concurrent data (fetch+Iceberg) tasks (default: --concurrency or 1)",
    )
    parser.add_argument(
        "--analytics-concurrency",
        type=int,
        default=None,
        help="Max concurrent analytics (Iceberg+export) tasks (default: --concurrency or data concurrency)",
    )
    parser.add_argument(
        "--rate-limit-min-interval",
        type=float,
        default=None,
        help="Minimum seconds between starting data tasks (per-process; protects upstream fetch)",
    )
    parser.add_argument(
        "--rate-limit-jitter",
        type=float,
        default=0.0,
        help="Random extra delay (seconds) added to the rate limiter (per-process)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Idempotent rerun: skip stages when run_result artifacts already exist for a params_hash",
    )
    args = parser.parse_args()

    os.chdir(_repo_root())
    max_workers = args.concurrency
    if args.data_concurrency or args.analytics_concurrency:
        max_workers = max(
            int(args.concurrency or 1),
            int(args.data_concurrency or 1),
            int(args.analytics_concurrency or 1),
        )
    if max_workers:
        batch_flow = run_batch.with_options(
            task_runner=ConcurrentTaskRunner(max_workers=int(max_workers))
        )
    else:
        batch_flow = run_batch

    rate_limit = None
    if args.rate_limit_min_interval is not None:
        rate_limit = {
            "enabled": True,
            "min_interval_seconds": float(args.rate_limit_min_interval),
            "jitter_seconds": float(args.rate_limit_jitter or 0.0),
        }

    result = batch_flow(
        args.batch,
        artifacts_dir=args.artifacts_dir,
        data_concurrency=args.data_concurrency,
        analytics_concurrency=args.analytics_concurrency,
        rate_limit=rate_limit,
        concurrency_hint=args.concurrency,
        skip_existing=bool(args.skip_existing),
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
