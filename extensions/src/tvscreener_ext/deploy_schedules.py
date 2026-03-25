from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prefect.runner import Runner
from prefect.schedules import Cron
from prefect.types.entrypoint import EntrypointType

from tvscreener_ext.upstream import ensure_upstream_tvscreener


@dataclass(frozen=True, slots=True)
class DeploymentSpec:
    name: str
    batch_path: str
    cron: str
    timezone: str = "UTC"


def _deployments(*, mode: str) -> list[DeploymentSpec]:
    if mode == "split-data":
        return [
            DeploymentSpec(
                name="opportunity-forex-majors-data",
                batch_path="tvscreener_ext/prefect/batches/forex_majors_data.json",
                cron="5 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-forex-minors-data",
                batch_path="tvscreener_ext/prefect/batches/forex_minors_data.json",
                cron="10 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-spot-majors-data",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_spot_majors_data.json",
                cron="15 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-perp-majors-data",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_perp_majors_data.json",
                cron="20 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-spot-minors-data",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_spot_minors_data.json",
                cron="25 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-perp-minors-data",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_perp_minors_data.json",
                cron="30 * * * *",
            ),
        ]

    if mode == "split-analytics":
        return [
            DeploymentSpec(
                name="opportunity-forex-majors-analytics",
                batch_path="tvscreener_ext/prefect/batches/forex_majors_analytics.json",
                cron="35 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-forex-minors-analytics",
                batch_path="tvscreener_ext/prefect/batches/forex_minors_analytics.json",
                cron="37 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-spot-majors-analytics",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_spot_majors_analytics.json",
                cron="40 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-perp-majors-analytics",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_perp_majors_analytics.json",
                cron="42 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-spot-minors-analytics",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_spot_minors_analytics.json",
                cron="45 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-perp-minors-analytics",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_perp_minors_analytics.json",
                cron="47 * * * *",
            ),
        ]

    if mode == "both":
        return [
            DeploymentSpec(
                name="opportunity-forex-majors-minors-both",
                batch_path="tvscreener_ext/prefect/batches/forex_majors_minors_both.json",
                cron="15 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-majors-minors-both",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_majors_minors_both.json",
                cron="25 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-market-risk-proxy-both",
                batch_path="tvscreener_ext/prefect/batches/market_risk_proxy_both.json",
                cron="*/15 * * * *",
            ),
        ]

    if mode == "analytics":
        return [
            DeploymentSpec(
                name="opportunity-forex-majors-minors-analytics",
                batch_path="tvscreener_ext/prefect/batches/forex_majors_minors_opportunity_analytics.json",
                cron="40 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-crypto-binance-majors-minors-analytics",
                batch_path="tvscreener_ext/prefect/batches/crypto_binance_majors_minors_analytics.json",
                cron="50 * * * *",
            ),
            DeploymentSpec(
                name="opportunity-market-risk-proxy-analytics",
                batch_path="tvscreener_ext/prefect/batches/market_risk_proxy_analytics.json",
                cron="7-59/15 * * * *",
            ),
        ]

    return [
        DeploymentSpec(
            name="opportunity-forex-majors-minors-data",
            batch_path="tvscreener_ext/prefect/batches/forex_majors_minors_data.json",
            cron="15 * * * *",
        ),
        DeploymentSpec(
            name="opportunity-crypto-binance-majors-minors-data",
            batch_path="tvscreener_ext/prefect/batches/crypto_binance_majors_minors_data.json",
            cron="25 * * * *",
        ),
        DeploymentSpec(
            name="opportunity-market-risk-proxy-data",
            batch_path="tvscreener_ext/prefect/batches/market_risk_proxy_data.json",
            cron="*/15 * * * *",
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    ensure_upstream_tvscreener()

    parser = argparse.ArgumentParser(
        description="Deploy scheduled tvscreener batch runs (extensions)"
    )
    parser.add_argument(
        "--work-pool", default=os.getenv("TVSCREENER_PREFECT_WORK_POOL", "tvscreener")
    )
    parser.add_argument(
        "--engine",
        choices=["runner", "worker"],
        default="runner",
        help="Deployment engine: runner (no worker) or worker (work pool)",
    )
    parser.add_argument(
        "--image",
        default=None,
        help="Worker engine: optional container image (docker pools)",
    )
    parser.add_argument(
        "--data-work-queue", default=os.getenv("TVSCREENER_PREFECT_DATA_QUEUE", "data")
    )
    parser.add_argument(
        "--work-queue",
        default=os.getenv("TVSCREENER_PREFECT_WORK_QUEUE", "default"),
        help="Worker engine: default work queue for deployments",
    )
    parser.add_argument(
        "--analytics-work-queue",
        default=os.getenv("TVSCREENER_PREFECT_ANALYTICS_QUEUE", "analytics"),
    )
    parser.add_argument(
        "--analytics-semantic-runtime",
        default=os.getenv("TVSCREENER_SEMANTIC_RUNTIME", "sidemantic"),
    )
    parser.add_argument(
        "--analytics-publish-table-artifacts",
        default=str(int((os.getenv("TVSCREENER_PUBLISH_TABLE_ARTIFACTS") or "1").strip() == "1")),
    )
    parser.add_argument(
        "--analytics-publish-results-summary",
        default=str(int((os.getenv("TVSCREENER_PUBLISH_RESULTS_SUMMARY") or "1").strip() == "1")),
    )
    parser.add_argument(
        "--lakehouse-base-dir",
        default=os.getenv("TVSCREENER_LAKEHOUSE_BASE_DIR", ".tvscreener/lakehouse"),
        help="Job env: TVSCREENER_LAKEHOUSE_BASE_DIR",
    )
    parser.add_argument(
        "--prefect-task-timeout-seconds",
        default=os.getenv("TVSCREENER_PREFECT_TASK_TIMEOUT_SECONDS", "1800"),
        help="Job env: TVSCREENER_PREFECT_TASK_TIMEOUT_SECONDS",
    )
    parser.add_argument("--paused", action="store_true")
    parser.add_argument(
        "--mode",
        choices=["data", "both", "analytics", "split-data", "split-analytics"],
        default="data",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--start-runner", action="store_true")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Runner engine only: poll once then exit",
    )
    parser.add_argument(
        "--working-dir",
        default=str(Path.cwd()),
        help="Working directory for deployments (default: cwd)",
    )

    args = parser.parse_args((sys.argv if argv is None else argv)[1:])

    # Import the flow only when needed so `--apply` can be dry-run
    # even if the upstream package lacks workflow modules.
    run_batch = None
    if args.apply or args.start_runner:
        from tvscreener_ext.prefect.run_batch import run_batch as _run_batch

        run_batch = _run_batch

    runner: Runner | None = None
    if str(args.engine) == "runner" and (args.apply or args.start_runner):
        runner = Runner(name="tvscreener")

    for d in _deployments(mode=str(args.mode)):
        schedule = Cron(d.cron, timezone=d.timezone)
        analytics_concurrency = 8
        if str(args.mode) in {"analytics", "split-analytics"}:
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

        job_variables: dict[str, Any] = {"working_dir": str(args.working_dir)}
        if str(args.mode) in {"analytics", "both", "split-analytics"}:
            env: dict[str, str] = {}
            if str(args.analytics_publish_table_artifacts).strip() == "1":
                env["TVSCREENER_PUBLISH_TABLE_ARTIFACTS"] = "1"
            if str(args.analytics_publish_results_summary).strip() == "1":
                env["TVSCREENER_PUBLISH_RESULTS_SUMMARY"] = "1"

            runtime = str(args.analytics_semantic_runtime or "").strip().lower()
            if runtime and runtime not in {"auto", "none"}:
                env["TVSCREENER_SEMANTIC_RUNTIME"] = runtime

            if env:
                job_variables["env"] = env

        # Always set lakehouse/task-timeout env for parity between local/remote workers.
        env = dict(job_variables.get("env") or {})
        base_dir = str(args.lakehouse_base_dir or "").strip()
        if base_dir:
            env["TVSCREENER_LAKEHOUSE_BASE_DIR"] = base_dir
        timeout_s = str(args.prefect_task_timeout_seconds or "").strip()
        if timeout_s:
            env["TVSCREENER_PREFECT_TASK_TIMEOUT_SECONDS"] = timeout_s
        if env:
            job_variables["env"] = env

        work_queue_name: str | None = None
        if str(args.engine) == "worker":
            default_queue = str(args.work_queue)
            if str(args.mode).startswith("split-"):
                work_queue_name = default_queue
            elif d.name.endswith("-data"):
                work_queue_name = (
                    str(args.data_work_queue) if args.data_work_queue else default_queue
                )
            elif d.name.endswith("-analytics"):
                work_queue_name = (
                    str(args.analytics_work_queue) if args.analytics_work_queue else default_queue
                )
            else:
                work_queue_name = default_queue

        if str(args.engine) == "worker":
            assert run_batch is not None
            image = str(args.image or "").strip() or None
            if image:
                job_variables = dict(job_variables)
                job_variables["image"] = image

            deployment = run_batch.to_deployment(
                name=d.name,
                schedules=[schedule],
                paused=bool(args.paused),
                parameters=params,
                tags=["tvscreener", "batch", "opportunity"],
                description=f"Scheduled batch: {d.batch_path}",
                work_pool_name=str(args.work_pool),
                work_queue_name=work_queue_name,
                job_variables=job_variables,
                entrypoint_type=EntrypointType.MODULE_PATH,
            )
            _deployment_id = deployment.apply()
            extra = f" image={image}" if image else ""
            print(f"applied engine=worker deployment={d.name} id={_deployment_id}{extra}")
        else:
            assert runner is not None
            assert run_batch is not None
            _deployment_id = runner.add_flow(
                flow=run_batch,
                name=d.name,
                schedules=[schedule],
                paused=bool(args.paused),
                parameters=params,
                tags=["tvscreener", "batch", "opportunity"],
                description=f"Scheduled batch: {d.batch_path}",
            )
            print(f"applied engine=runner deployment={d.name} id={_deployment_id}")

    if runner is not None and args.start_runner:
        asyncio.run(runner.start(run_once=bool(args.run_once)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
