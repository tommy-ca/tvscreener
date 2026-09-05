from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from tvscreener_ext import scan


def _default_env() -> None:
    load_dotenv(override=False)
    os.environ.setdefault("PREFECT_API_URL", "http://127.0.0.1:4200/api")
    os.environ.setdefault("PREFECT_HOME", os.path.join(os.getcwd(), ".prefect-home"))
    os.environ.setdefault("TVSCREENER_PUBLISH_TABLE_ARTIFACTS", "1")
    os.environ.setdefault("TVSCREENER_PUBLISH_RESULTS_SUMMARY", "1")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run essential pipeline validation runset")
    parser.add_argument(
        "--runner",
        choices=["prefect", "local"],
        default="prefect",
        help="Execute via Prefect flow runs or in-process",
    )
    parser.add_argument(
        "--mode",
        choices=["both", "analytics"],
        default="both",
        help="Run data+analytics (both) or analytics-only rerender",
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--timeframes", default="240,60,15")
    parser.add_argument("--matrix", action="store_true", default=True)
    args = parser.parse_args((sys.argv if argv is None else argv)[1:])

    _default_env()

    pipeline = "both" if args.mode == "both" else "analytics"
    tf = str(args.timeframes)
    limit = str(int(args.limit))
    matrix_flags = ["--matrix", "--limit", limit] if bool(args.matrix) else []

    runset: list[list[str]] = [
        [
            "tvscreener-ext-scan",
            "--runner",
            str(args.runner),
            "--scanner",
            "opportunity",
            "--pipeline",
            pipeline,
            "--asset-type",
            "forex",
            "--universe",
            "majors",
            "--timeframes",
            tf,
            *matrix_flags,
        ],
        [
            "tvscreener-ext-scan",
            "--runner",
            str(args.runner),
            "--scanner",
            "opportunity",
            "--pipeline",
            pipeline,
            "--asset-type",
            "forex",
            "--universe",
            "minors",
            "--timeframes",
            tf,
            *matrix_flags,
        ],
        [
            "tvscreener-ext-scan",
            "--runner",
            str(args.runner),
            "--scanner",
            "opportunity",
            "--pipeline",
            pipeline,
            "--asset-type",
            "crypto",
            "--instrument-type",
            "spot",
            "--universe",
            "majors",
            "--timeframes",
            tf,
            *matrix_flags,
        ],
        [
            "tvscreener-ext-scan",
            "--runner",
            str(args.runner),
            "--scanner",
            "opportunity",
            "--pipeline",
            pipeline,
            "--asset-type",
            "crypto",
            "--instrument-type",
            "perp",
            "--universe",
            "majors",
            "--timeframes",
            tf,
            *matrix_flags,
        ],
        [
            "tvscreener-ext-scan",
            "--runner",
            str(args.runner),
            "--scanner",
            "opportunity",
            "--pipeline",
            pipeline,
            "--asset-type",
            "crypto",
            "--instrument-type",
            "spot",
            "--universe",
            "minors",
            "--timeframes",
            tf,
            *matrix_flags,
        ],
        [
            "tvscreener-ext-scan",
            "--runner",
            str(args.runner),
            "--scanner",
            "opportunity",
            "--pipeline",
            pipeline,
            "--asset-type",
            "crypto",
            "--instrument-type",
            "perp",
            "--universe",
            "minors",
            "--timeframes",
            tf,
            *matrix_flags,
        ],
        [
            "tvscreener-ext-scan",
            "--runner",
            str(args.runner),
            "--scanner",
            "opportunity",
            "--pipeline",
            pipeline,
            "--asset-type",
            "stock",
            "--universe",
            "market_risk",
            "--timeframes",
            tf,
            *matrix_flags,
        ],
    ]

    rc = 0
    for cmd in runset:
        step_rc = scan.main(cmd)
        if step_rc != 0:
            rc = step_rc
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
