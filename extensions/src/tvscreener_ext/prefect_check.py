from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import WorkPoolFilter, WorkPoolFilterName


@dataclass(frozen=True, slots=True)
class ScheduledRun:
    deployment_id: str
    deployment_name: str | None
    flow_run_id: str
    scheduled_time: str | None


def _api_url() -> str:
    return (os.getenv("PREFECT_API_URL") or "http://127.0.0.1:4200/api").rstrip("/")


def _safe_deployment_name(name: str | None) -> str | None:
    if not name:
        return None
    return f"tvscreener-batch/{name}" if not name.startswith("tvscreener-batch/") else name


async def _check(
    *,
    pool: str,
    work_queues: list[str],
    limit: int,
    lookahead_minutes: int,
) -> int:
    print(f"prefect_api=url {_api_url()}")

    async with get_client() as client:
        # Queues
        for q in work_queues:
            try:
                qobj = await client.read_work_queue_by_name(q, work_pool_name=pool)
                print(
                    f"work_queue=ok pool={pool} queue={q} is_paused={getattr(qobj, 'is_paused', None)}"
                )
            except Exception:
                print(f"work_queue=unknown pool={pool} queue={q}")

        # Workers
        try:
            workers = await client.read_workers_for_work_pool(pool, limit=10)
            print(f"workers=count {len(workers)} pool={pool}")
        except Exception as exc:
            print(f"workers=error pool={pool} err={exc}")

        # Deployments scoped to pool
        dep_by_id: dict[str, str | None] = {}
        try:
            deps = await client.read_deployments(
                work_pool_filter=WorkPoolFilter(name=WorkPoolFilterName(any_=[pool])),
                limit=200,
            )

            def _status_str(d: object) -> str:
                st = getattr(d, "status", None)
                return str(getattr(st, "value", st) or "")

            not_ready = [d for d in deps if _status_str(d).upper() != "READY"]
            print(f"deployments=count {len(deps)} pool={pool} not_ready={len(not_ready)}")
            for d in deps[:10]:
                name = getattr(d, "name", None)
                status = _status_str(d)
                sched = getattr(d, "schedules", None) or []
                print(f"- deployment={name} status={status} schedules={len(sched)}")
            for d in deps:
                dep_by_id[str(d.id)] = _safe_deployment_name(
                    cast(str | None, getattr(d, "name", None))
                )
        except Exception as exc:
            print(f"deployments=error pool={pool} err={exc}")

        # Scheduled work preview via API
        now = datetime.now(tz=UTC)
        scheduled_before = now + timedelta(minutes=int(lookahead_minutes))
        try:
            scheduled = await client.get_scheduled_flow_runs_for_work_pool(
                pool,
                work_queue_names=work_queues,
                scheduled_before=scheduled_before,
            )
        except Exception as exc:
            print(f"scheduled_runs=error pool={pool} queue={','.join(work_queues)} err={exc}")
            return 3

        runs: list[ScheduledRun] = []
        for item in scheduled:
            fr = item.flow_run
            dep_id = getattr(fr, "deployment_id", None)
            if not dep_id:
                continue
            runs.append(
                ScheduledRun(
                    deployment_id=str(dep_id),
                    deployment_name=dep_by_id.get(str(dep_id)),
                    flow_run_id=str(getattr(fr, "id", "")),
                    scheduled_time=str(getattr(fr, "expected_start_time", None) or ""),
                )
            )

        runs = sorted(runs, key=lambda r: str(r.scheduled_time or ""))[: int(limit)]
        print(f"scheduled_runs=count {len(runs)} pool={pool} queue={','.join(work_queues)}")
        for r in runs:
            dep = r.deployment_name or r.deployment_id
            when = r.scheduled_time or "unknown"
            print(f"- {dep} flow_run_id={r.flow_run_id} at={when}")

    return 0


def check_main(argv: list[str]) -> int:
    pool = "tvscreener"
    work_queue = "default"
    limit = 10
    lookahead_minutes = 90

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
                "Usage: ... [--pool=...] [--work-queue=...] [--limit=N] [--lookahead-minutes=N]"
            )

    queues = [q.strip() for q in str(work_queue).split(",") if q.strip()]
    return int(
        asyncio.run(
            _check(
                pool=str(pool),
                work_queues=queues,
                limit=int(limit),
                lookahead_minutes=int(lookahead_minutes),
            )
        )
    )


def main(argv: list[str] | None = None) -> int:
    return int(check_main(sys.argv if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
