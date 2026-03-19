from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Ensure repo root is importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workflows.prefect.config import load_config, repo_root


def _env() -> dict[str, str]:
    cfg = load_config()
    env = dict(os.environ)
    env["PREFECT_HOME"] = str(cfg.prefect_home)
    env["PREFECT_API_URL"] = cfg.api_url
    return env


def _run(args: list[str]) -> int:
    proc = subprocess.run(args, env=_env(), check=False)
    return int(proc.returncode)


def _run_prefect(prefect_args: list[str]) -> int:
    return _run(["uv", "run", "prefect", *prefect_args])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Repo-local Prefect helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    server = sub.add_parser("server", help="Start/stop Prefect server")
    server_sub = server.add_subparsers(dest="server_cmd", required=True)
    server_start = server_sub.add_parser("start", help="Start Prefect server")
    server_start.add_argument("--background", action="store_true")
    server_sub.add_parser("stop", help="Stop Prefect server")

    worker = sub.add_parser("worker", help="Start a Prefect worker")
    worker.add_argument("--queue", required=True, help="Work queue name")
    worker.add_argument("--limit", type=int, default=1)
    worker.add_argument("--run-once", action="store_true")

    apply = sub.add_parser("apply", help="Apply deployments to pool/queues")
    apply.add_argument("--mode", choices=["data", "analytics", "both"], required=True)

    check = sub.add_parser("check", help="Check queues and scheduled runs")
    check.add_argument(
        "--work-queue",
        default=None,
        help="Comma-separated work queues (default: data,analytics)",
    )
    check.add_argument("--limit", type=int, default=10)
    check.add_argument("--lookahead-minutes", type=int, default=90)

    args = parser.parse_args(argv[1:])
    cfg = load_config()

    if args.cmd == "server":
        if args.server_cmd == "start":
            prefect_args = [
                "server",
                "start",
                "--host",
                cfg.api_host,
                "--port",
                str(cfg.api_port),
            ]
            if args.background:
                prefect_args.append("--background")
            return _run_prefect(prefect_args)

        if args.server_cmd == "stop":
            return _run_prefect(["server", "stop"])

    if args.cmd == "worker":
        prefect_args = [
            "worker",
            "start",
            "--pool",
            cfg.work_pool,
            "--work-queue",
            str(args.queue),
            "--limit",
            str(int(args.limit)),
            "--no-prompt",
        ]
        if args.run_once:
            prefect_args.append("--run-once")
        return _run_prefect(prefect_args)

    if args.cmd == "apply":
        # Ensure repo root is the working directory so relative batch paths work.
        proc = subprocess.run(
            [
                "uv",
                "run",
                "python3",
                "workflows/prefect/deploy_schedules.py",
                "--apply",
                "--mode",
                str(args.mode),
                "--engine",
                "worker",
                "--work-pool",
                cfg.work_pool,
                "--data-work-queue",
                cfg.data_work_queue,
                "--analytics-work-queue",
                cfg.analytics_work_queue,
            ],
            env=_env(),
            cwd=str(repo_root()),
            check=False,
        )
        return int(proc.returncode)

    if args.cmd == "check":
        wq = args.work_queue or f"{cfg.data_work_queue},{cfg.analytics_work_queue}"
        proc = subprocess.run(
            [
                "uv",
                "run",
                "python3",
                "workflows/prefect/check_schedules.py",
                f"--pool={cfg.work_pool}",
                f"--work-queue={wq}",
                f"--limit={int(args.limit)}",
                f"--lookahead-minutes={int(args.lookahead_minutes)}",
            ],
            env=_env(),
            cwd=str(repo_root()),
            check=False,
        )
        return int(proc.returncode)

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
