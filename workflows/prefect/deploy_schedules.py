from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prefect.runner import Runner
from prefect.schedules import Cron


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


# Ensure repo root is importable when run as a script.
sys.path.insert(0, str(_repo_root()))

from workflows.prefect.config import load_config  # noqa: E402
from workflows.prefect.run_batch import run_batch  # noqa: E402

# `run_batch` is a Prefect Flow object at runtime.
_RUN_BATCH_FLOW: Any = run_batch


@dataclass(frozen=True, slots=True)
class DeploymentSpec:
    name: str
    batch_path: str
    cron: str
    timezone: str = "UTC"


_CFG = load_config()
DEFAULT_WORK_POOL = _CFG.work_pool
DEFAULT_DATA_WORK_QUEUE = _CFG.data_work_queue
DEFAULT_ANALYTICS_WORK_QUEUE = _CFG.analytics_work_queue


def _deployments(*, mode: str) -> list[DeploymentSpec]:
    # Conservative defaults; adjust cron to your ops cadence.
    if mode == "both":
        return [
            DeploymentSpec(
                name="opportunity-forex-majors-minors-both",
                batch_path="workflows/prefect/batches/forex_majors_minors_both.json",
                cron="15 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-majors-minors-both",
                batch_path="workflows/prefect/batches/crypto_binance_majors_minors_both.json",
                cron="25 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-market-risk-proxy-both",
                batch_path="workflows/prefect/batches/market_risk_proxy_both.json",
                cron="*/15 * * * *",
            ),
        ]

    if mode == "analytics":
        return [
            DeploymentSpec(
                name="opportunity-forex-majors-minors-analytics",
                batch_path="workflows/prefect/batches/forex_majors_minors_opportunity_analytics.json",
                cron="40 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-majors-minors-analytics",
                batch_path="workflows/prefect/batches/crypto_binance_majors_minors_analytics.json",
                cron="50 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-market-risk-proxy-analytics",
                batch_path="workflows/prefect/batches/market_risk_proxy_analytics.json",
                cron="7-59/15 * * * *",
            ),
        ]

    # Default: schedule only data pipelines.
    return [
        DeploymentSpec(
            name="opportunity-forex-majors-minors-data",
            batch_path="workflows/prefect/batches/forex_majors_minors_data.json",
            cron="15 * * * *",
        ),
        DeploymentSpec(
            name="opportunity-crypto-binance-majors-minors-data",
            batch_path="workflows/prefect/batches/crypto_binance_majors_minors_data.json",
            cron="25 * * * *",
        ),
        DeploymentSpec(
            name="opportunity-market-risk-proxy-data",
            batch_path="workflows/prefect/batches/market_risk_proxy_data.json",
            cron="*/15 * * * *",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy scheduled tvscreener batch runs")
    parser.add_argument(
        "--work-pool",
        default=DEFAULT_WORK_POOL,
        help="Work pool name (used for worker deployments)",
    )
    parser.add_argument(
        "--engine",
        choices=["runner", "worker"],
        default="runner",
        help="Deployment engine: runner (no worker) or worker (work pool)",
    )
    parser.add_argument(
        "--data-work-queue",
        default=DEFAULT_DATA_WORK_QUEUE,
        help="Work queue name for data deployments (default: data)",
    )
    parser.add_argument(
        "--analytics-work-queue",
        default=DEFAULT_ANALYTICS_WORK_QUEUE,
        help="Work queue name for analytics deployments (default: analytics)",
    )
    parser.add_argument(
        "--paused",
        action="store_true",
        help="Create deployments in a paused state",
    )
    parser.add_argument(
        "--mode",
        choices=["data", "both", "analytics"],
        default="data",
        help="Which pipeline mode to schedule (default: data only)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deployments to Prefect (default: dry-run print only)",
    )
    parser.add_argument(
        "--start-runner",
        action="store_true",
        help="Start a Prefect Runner to execute schedules (blocks)",
    )
    args = parser.parse_args()

    runner: Runner | None = None
    if str(args.engine) == "runner" and (args.apply or args.start_runner):
        runner = Runner(name="tvscreener")

    for d in _deployments(mode=str(args.mode)):
        schedule = Cron(d.cron, timezone=d.timezone)
        analytics_concurrency = 8
        if str(args.mode) == "analytics":
            analytics_concurrency = 1

        params = {
            "batch_path": d.batch_path,
            "artifacts_dir": "artifacts/runs",
            "data_concurrency": 1,
            "analytics_concurrency": analytics_concurrency,
            "rate_limit": {
                "enabled": True,
                "min_interval_seconds": 1.0,
                "jitter_seconds": 0.25,
            },
            "skip_existing": False,
        }

        if not args.apply:
            print(
                f"DRY_RUN name={d.name} pool={args.work_pool} cron={d.cron} tz={d.timezone} paused={args.paused} params={params}"
            )
            continue

        job_variables: dict[str, Any] = {"working_dir": str(_repo_root())}
        if str(args.mode) == "analytics":
            job_variables["env"] = {
                "TVSCREENER_PUBLISH_TABLE_ARTIFACTS": "1",
                # Semantic runtime defaults to auto (Sidemantic if installed).
            }

        work_queue_name: str | None = None
        if str(args.engine) == "worker":
            if d.name.endswith("-data"):
                work_queue_name = str(args.data_work_queue)
            elif d.name.endswith("-analytics"):
                work_queue_name = str(args.analytics_work_queue)
            else:
                # both runs write to Iceberg; keep on the data queue.
                work_queue_name = str(args.data_work_queue)

        if str(args.engine) == "worker":
            deployment = _RUN_BATCH_FLOW.to_deployment(
                name=d.name,
                schedules=[schedule],
                paused=bool(args.paused),
                parameters=params,
                tags=["tvscreener", "batch", "opportunity"],
                description=f"Scheduled batch: {d.batch_path}",
                work_pool_name=str(args.work_pool),
                work_queue_name=work_queue_name,
                job_variables=job_variables,
            )
            _deployment_id = deployment.apply()
        else:
            assert runner is not None
            runner.add_flow(
                flow=_RUN_BATCH_FLOW,
                name=d.name,
                schedules=[schedule],
                paused=bool(args.paused),
                parameters=params,
                tags=["tvscreener", "batch", "opportunity"],
                description=f"Scheduled batch: {d.batch_path}",
            )

    if str(args.engine) != "runner" and args.start_runner:
        raise SystemExit("--start-runner is only supported with --engine runner")

    if args.start_runner:
        assert runner is not None

        async def _start() -> None:
            await runner.start()

        asyncio.run(_start())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
