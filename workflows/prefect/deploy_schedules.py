from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from prefect.schedules import Cron


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


# Ensure repo root is importable when run as a script.
sys.path.insert(0, str(_repo_root()))

from workflows.prefect.run_batch import run_batch  # noqa: E402


@dataclass(frozen=True, slots=True)
class DeploymentSpec:
    name: str
    batch_path: str
    cron: str
    timezone: str = "UTC"


DEFAULT_WORK_POOL = "tvscreener"


def _deployments() -> list[DeploymentSpec]:
    # Conservative defaults; adjust cron to your ops cadence.
    return [
        DeploymentSpec(
            name="opportunity-forex-majors-minors",
            batch_path="workflows/prefect/batches/forex_majors_minors_both.json",
            cron="15 * * * *",
        ),
        DeploymentSpec(
            name="opportunity-crypto-binance-majors-minors",
            batch_path="workflows/prefect/batches/crypto_binance_majors_minors_both.json",
            cron="25 * * * *",
        ),
        DeploymentSpec(
            name="opportunity-market-risk-proxy",
            batch_path="workflows/prefect/batches/market_risk_proxy_both.json",
            cron="*/15 * * * *",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy scheduled tvscreener batch runs")
    parser.add_argument(
        "--work-pool",
        default=DEFAULT_WORK_POOL,
        help="Prefect work pool name (process worker recommended)",
    )
    parser.add_argument(
        "--paused",
        action="store_true",
        help="Create deployments in a paused state",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deployments to Prefect (default: dry-run print only)",
    )
    args = parser.parse_args()

    for d in _deployments():
        schedule = Cron(d.cron, timezone=d.timezone)
        params = {
            "batch_path": d.batch_path,
            "artifacts_dir": "artifacts/runs",
            "data_concurrency": 1,
            "analytics_concurrency": 8,
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

        run_batch.deploy(
            name=d.name,
            work_pool_name=str(args.work_pool),
            schedules=[schedule],
            paused=bool(args.paused),
            parameters=params,
            # This repo uses uv + process workers; no image build.
            build=False,
            push=False,
            tags=["tvscreener", "batch", "opportunity"],
            description=f"Scheduled batch: {d.batch_path}",
            print_next_steps=False,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
