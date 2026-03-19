from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class ScheduledRun:
    deployment_id: str
    deployment_name: str | None
    flow_run_id: str
    flow_run_name: str | None
    scheduled_time: str | None
    state_type: str | None


def _api_url() -> str:
    # Prefer shared config defaults.
    try:
        from workflows.prefect.config import load_config

        return load_config().api_url.rstrip("/")
    except Exception:
        return (os.getenv("PREFECT_API_URL") or "http://127.0.0.1:4200/api").rstrip("/")


def _get_json(url: str) -> Any:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)


def _post_json(url: str, payload: dict[str, Any]) -> Any:
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        method="POST",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(req, timeout=20) as resp:
        return json.load(resp)


def _safe_name(deployment: dict[str, Any]) -> str | None:
    name = deployment.get("name")
    if not name:
        return None
    # Prefect API returns name without flow prefix; match CLI display.
    return f"tvscreener-batch/{name}" if not name.startswith("tvscreener-batch/") else name


def list_scheduled_runs(
    *,
    pool: str,
    work_queue: str,
    limit: int,
    lookahead_minutes: int,
) -> list[ScheduledRun]:
    now = datetime.now(tz=UTC)
    scheduled_before = (now + timedelta(minutes=int(lookahead_minutes))).isoformat()
    url = f"{_api_url()}/work_pools/{pool}/get_scheduled_flow_runs"
    payload = {
        "work_queue_names": [work_queue],
        "scheduled_before": scheduled_before,
        "limit": int(limit),
    }

    items = _post_json(url, payload)
    out: list[ScheduledRun] = []
    for item in items:
        fr = item.get("flow_run") or {}
        dep_id = fr.get("deployment_id")
        if not dep_id:
            continue
        out.append(
            ScheduledRun(
                deployment_id=str(dep_id),
                deployment_name=None,
                flow_run_id=str(fr.get("id")),
                flow_run_name=fr.get("name"),
                scheduled_time=fr.get("expected_start_time") or fr.get("next_scheduled_start_time"),
                state_type=(fr.get("state") or {}).get("type"),
            )
        )

    # Hydrate deployment names with a filter call.
    if out:
        dep_ids = sorted({r.deployment_id for r in out})
        dep_filter_url = f"{_api_url()}/deployments/filter"
        dep_resp = _post_json(
            dep_filter_url,
            {
                "deployments": {"id": {"any_": dep_ids}},
                "limit": len(dep_ids),
            },
        )
        by_id: dict[str, str | None] = {}
        for d in dep_resp:
            did = str(d.get("id"))
            by_id[did] = _safe_name(d)

        out = [
            ScheduledRun(
                deployment_id=r.deployment_id,
                deployment_name=by_id.get(r.deployment_id),
                flow_run_id=r.flow_run_id,
                flow_run_name=r.flow_run_name,
                scheduled_time=r.scheduled_time,
                state_type=r.state_type,
            )
            for r in out
        ]

    return out


def list_workers(*, pool: str, limit: int = 10) -> list[dict[str, Any]]:
    url = f"{_api_url()}/work_pools/{pool}/workers/filter"
    payload = {
        "workers": {},
        "limit": int(limit),
        "sort": "LAST_SEEN_DESC",
    }
    return _post_json(url, payload)


def get_queue(*, pool: str, work_queue: str) -> dict[str, Any] | None:
    url = f"{_api_url()}/work_pools/{pool}/queues/{work_queue}"
    try:
        return _get_json(url)
    except Exception:
        return None


def main(argv: list[str]) -> int:
    pool = "tvscreener"
    work_queue = "default"
    limit = 10
    lookahead_minutes = 90

    # Keep parsing simple; this is an ops check.
    for arg in argv[1:]:
        if arg.startswith("--pool="):
            pool = arg.split("=", 1)[1]
        elif arg.startswith("--work-queue="):
            work_queue = arg.split("=", 1)[1]
        elif arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
        elif arg.startswith("--lookahead-minutes="):
            lookahead_minutes = int(arg.split("=", 1)[1])
        else:
            raise SystemExit(
                "Usage: check_schedules.py [--pool=...] [--work-queue=...] [--limit=N] [--lookahead-minutes=N]"
            )

    # Server readiness
    ready_url = f"{_api_url()}/ready"
    try:
        _get_json(ready_url)
    except Exception as exc:
        print(f"prefect_api=not_ready url={ready_url} err={exc}")
        return 2

    print(f"prefect_api=ready url={_api_url()}")

    queue_names = [q.strip() for q in work_queue.split(",") if q.strip()]
    for q in queue_names:
        queue_obj = get_queue(pool=pool, work_queue=q)
        if queue_obj is None:
            print(f"work_queue=unknown pool={pool} queue={q}")
        else:
            print(f"work_queue=ok pool={pool} queue={q} is_paused={queue_obj.get('is_paused')}")

    try:
        workers = list_workers(pool=pool, limit=10)
        print(f"workers=count {len(workers)} pool={pool}")
        for w in workers:
            print(
                f"- {w.get('name')} type={w.get('type')} status={w.get('status')} last_seen={w.get('last_seen')}"
            )
    except Exception as exc:
        print(f"workers=error pool={pool} err={exc}")

    # Scheduled runs
    try:
        runs: list[ScheduledRun] = []
        for q in queue_names:
            runs.extend(
                list_scheduled_runs(
                    pool=pool,
                    work_queue=q,
                    limit=limit,
                    lookahead_minutes=lookahead_minutes,
                )
            )
        runs = runs[:limit]
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        print(
            f"scheduled_runs=error pool={pool} queue={work_queue} status={exc.code} body={body[:200]}"
        )
        return 3
    except Exception as exc:
        print(f"scheduled_runs=error pool={pool} queue={work_queue} err={exc}")
        return 3

    print(f"scheduled_runs=count {len(runs)} pool={pool} queue={work_queue}")
    for r in runs:
        dep = r.deployment_name or r.deployment_id
        when = r.scheduled_time or "unknown"
        state = r.state_type or "unknown"
        print(f"- {dep} flow_run={r.flow_run_name or r.flow_run_id} state={state} at={when}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
