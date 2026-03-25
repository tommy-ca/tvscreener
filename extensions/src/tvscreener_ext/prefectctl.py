from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


def _env() -> dict[str, str]:
    load_dotenv(override=False)
    env = dict(os.environ)

    # Keep Prefect state isolated by default.
    env.setdefault("PREFECT_HOME", str(Path.cwd() / ".prefect-home"))
    env.setdefault("PREFECT_API_URL", "http://127.0.0.1:4200/api")

    # Defaults for worker deployments.
    env.setdefault("TVSCREENER_PREFECT_WORK_POOL", "tvscreener")
    env.setdefault("TVSCREENER_PREFECT_WORK_QUEUE", "default")
    env.setdefault("TVSCREENER_PREFECT_DATA_QUEUE", "data")
    env.setdefault("TVSCREENER_PREFECT_ANALYTICS_QUEUE", "analytics")
    return env


def _load_env() -> None:
    # Ensure `.env` is applied before importing Prefect.
    _ = _env()


def _wait_for_server_ready(*, url: str, timeout_seconds: int = 30) -> bool:
    deadline = time.time() + float(timeout_seconds)
    while time.time() < deadline:
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=2) as _resp:
                return True
        except URLError:
            time.sleep(0.5)
        except Exception:
            time.sleep(0.5)
    return False


def _parse_iso(dt: str) -> datetime | None:
    try:
        s = str(dt).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(s)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


def _api_url() -> str:
    return str(_env().get("PREFECT_API_URL") or "http://127.0.0.1:4200/api").rstrip("/")


def _post_json(url: str, payload: dict[str, object]) -> object:
    import json

    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        method="POST",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(req, timeout=20) as resp:
        return json.load(resp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prefect helper (extensions)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    server = sub.add_parser("server", help="Start/stop Prefect server")
    server_sub = server.add_subparsers(dest="server_cmd", required=True)
    server_start = server_sub.add_parser("start", help="Start Prefect server")
    server_start.add_argument("--host", default="127.0.0.1")
    server_start.add_argument("--port", default="4200")
    server_start.add_argument("--background", action="store_true")
    server_ensure = server_sub.add_parser("ensure", help="Start server if not ready")
    server_ensure.add_argument("--host", default="127.0.0.1")
    server_ensure.add_argument("--port", default="4200")
    server_ensure.add_argument("--background", action="store_true")
    server_sub.add_parser("stop", help="Stop Prefect server")

    pool = sub.add_parser("pool", help="Create pool and queues")
    pool.add_argument("--name", default=os.getenv("TVSCREENER_PREFECT_WORK_POOL", "tvscreener"))
    pool.add_argument(
        "--type",
        default="process",
        help="Prefect worker pool type (default: process)",
    )
    pool.add_argument(
        "--data-queue",
        default=os.getenv("TVSCREENER_PREFECT_DATA_QUEUE", "data"),
    )
    pool.add_argument(
        "--analytics-queue",
        default=os.getenv("TVSCREENER_PREFECT_ANALYTICS_QUEUE", "analytics"),
    )

    worker = sub.add_parser("worker", help="Start a Prefect worker")
    worker.add_argument(
        "--pool",
        default=os.getenv("TVSCREENER_PREFECT_WORK_POOL", "tvscreener"),
    )
    worker.add_argument("--queue", required=True, help="Work queue name")
    worker.add_argument("--limit", type=int, default=1)
    worker.add_argument("--run-once", action="store_true")

    check = sub.add_parser("check", help="Check queues and scheduled runs")
    check.add_argument(
        "--pool",
        default=os.getenv("TVSCREENER_PREFECT_WORK_POOL", "tvscreener"),
    )
    check.add_argument(
        "--work-queue",
        default=None,
        help="Comma-separated work queues (default: TVSCREENER_PREFECT_WORK_QUEUE or 'default')",
    )
    check.add_argument("--limit", type=int, default=10)
    check.add_argument("--lookahead-minutes", type=int, default=90)

    prune = sub.add_parser("prune-late", help="Cancel late scheduled flow runs")
    prune.add_argument(
        "--pool",
        default=os.getenv("TVSCREENER_PREFECT_WORK_POOL", "tvscreener"),
    )
    prune.add_argument(
        "--work-queue",
        default=str(_env().get("TVSCREENER_PREFECT_WORK_QUEUE") or "default"),
    )
    prune.add_argument(
        "--older-than-minutes",
        type=int,
        default=30,
        help="Cancel SCHEDULED runs older than this many minutes",
    )
    prune.add_argument("--limit", type=int, default=200)
    prune.add_argument("--dry-run", action="store_true")

    artifacts = sub.add_parser("artifacts", help="List Prefect artifacts")
    artifacts.add_argument(
        "--key-like",
        default="tvscreener-%",
        help="SQL LIKE pattern for artifact key (default: tvscreener-%%)",
    )
    artifacts.add_argument(
        "--type",
        default=None,
        help="Artifact type filter (example: markdown or table)",
    )
    artifacts.add_argument("--limit", type=int, default=20)

    args = parser.parse_args((sys.argv if argv is None else argv)[1:])

    _load_env()

    if args.cmd == "server":
        from prefect.cli import server as server_cli

        if args.server_cmd == "start":
            try:
                server_cli.start(
                    host=str(args.host),
                    port=int(args.port),
                    scheduler=True,
                    background=bool(args.background),
                )
            except SystemExit as exc:
                # Prefect's CLI entrypoints may call sys.exit(). Treat as failure.
                return int(getattr(exc, "code", 1) or 1)
            except Exception as exc:
                print(f"server_start=error err={exc}")
                return 1

            if args.background:
                ready_url = f"{_env()['PREFECT_API_URL'].rstrip('/')}/ready"
                _wait_for_server_ready(url=ready_url, timeout_seconds=30)
            return 0

        if args.server_cmd == "ensure":
            ready_url = f"{_env()['PREFECT_API_URL'].rstrip('/')}/ready"
            if _wait_for_server_ready(url=ready_url, timeout_seconds=1):
                print(f"server=ready url={ready_url}")
                return 0
            print(f"server=starting url={ready_url}")
            try:
                server_cli.start(
                    host=str(args.host),
                    port=int(args.port),
                    scheduler=True,
                    background=bool(args.background),
                )
            except SystemExit as exc:
                return int(getattr(exc, "code", 1) or 1)
            except Exception as exc:
                print(f"server_start=error err={exc}")
                return 1
            if args.background:
                _wait_for_server_ready(url=ready_url, timeout_seconds=30)
            return 0
        if args.server_cmd == "stop":
            try:
                server_cli.stop()
            except SystemExit as exc:
                return int(getattr(exc, "code", 1) or 1)
            except Exception as exc:
                print(f"server_stop=error err={exc}")
                return 1
            return 0

    if args.cmd == "pool":
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.actions import WorkPoolCreate

        async def _run() -> int:
            async with get_client() as client:
                await client.create_work_pool(
                    WorkPoolCreate(name=str(args.name), type=str(args.type)),
                    overwrite=True,
                )
                # Ensure queues exist.
                for q in {
                    str(args.data_queue),
                    str(args.analytics_queue),
                    str(_env().get("TVSCREENER_PREFECT_WORK_QUEUE") or "default"),
                }:
                    try:
                        await client.read_work_queue_by_name(q, work_pool_name=str(args.name))
                    except Exception:
                        await client.create_work_queue(q, work_pool_name=str(args.name))
            return 0

        return int(asyncio.run(_run()))

    if args.cmd == "worker":
        from prefect.workers.process import ProcessWorker

        async def _run() -> None:
            worker = ProcessWorker(
                work_pool_name=str(args.pool),
                work_queues=[str(args.queue)],
                limit=int(args.limit),
            )
            await worker.start(run_once=bool(args.run_once))

        asyncio.run(_run())
        return 0

    if args.cmd == "check":
        from tvscreener_ext.prefect_check import check_main

        wq = args.work_queue or str(_env().get("TVSCREENER_PREFECT_WORK_QUEUE") or "default")
        return int(
            check_main(
                [
                    "tvscreener-prefectctl-check",
                    f"--pool={args.pool}",
                    f"--work-queue={wq}",
                    f"--limit={int(args.limit)}",
                    f"--lookahead-minutes={int(args.lookahead_minutes)}",
                ]
            )
        )

    if args.cmd == "prune-late":
        from prefect.client.orchestration import get_client
        from prefect.states import Cancelled

        pool_name = str(args.pool)
        work_queue = str(args.work_queue)
        older = int(args.older_than_minutes)
        deadline = datetime.now(tz=UTC) - timedelta(minutes=older)

        async def _run() -> int:
            async with get_client() as client:
                scheduled = await client.get_scheduled_flow_runs_for_work_pool(
                    pool_name,
                    work_queue_names=[work_queue],
                    scheduled_before=datetime.now(tz=UTC) + timedelta(hours=24),
                )
                late_ids: list[str] = []
                for item in scheduled:
                    fr = item.flow_run
                    est = getattr(fr, "expected_start_time", None)
                    if est and est < deadline:
                        late_ids.append(str(fr.id))

                print(
                    f"prune_late queue={work_queue} older_than_minutes={older} late={len(late_ids)}"
                )
                for rid in late_ids[:25]:
                    print(f"- flow_run_id={rid}")

                if args.dry_run:
                    return 0

                cancelled = 0
                for rid in late_ids:
                    try:
                        await client.set_flow_run_state(rid, state=Cancelled())
                        cancelled += 1
                    except Exception:
                        continue
                print(f"prune_late_cancelled count={cancelled}")
                return 0

        return int(asyncio.run(_run()))

    if args.cmd == "artifacts":
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.filters import (
            ArtifactFilter,
            ArtifactFilterKey,
            ArtifactFilterType,
        )

        key_like = str(args.key_like)
        type_name = (str(args.type) if args.type is not None else "").strip() or None

        async def _run() -> int:
            async with get_client() as client:
                flt = ArtifactFilter(key=ArtifactFilterKey(like_=key_like))
                if type_name:
                    flt.type = ArtifactFilterType(any_=[type_name])
                arts = await client.read_artifacts(limit=int(args.limit), artifact_filter=flt)
                print(f"artifacts=count {len(arts)} key_like={key_like} type={type_name or 'any'}")
                for a in arts:
                    updated = getattr(a, "updated", None) or getattr(a, "created", None)
                    print(
                        f"- id={a.id} type={a.type} key={a.key} updated={updated} flow_run_id={getattr(a, 'flow_run_id', None)}"
                    )
            return 0

        return int(asyncio.run(_run()))

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
