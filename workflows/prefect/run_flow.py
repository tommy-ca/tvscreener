from __future__ import annotations

import argparse
import json
from pathlib import Path

from tvscreener.lib.pipeline_runner import PipelineRunSpec
from tvscreener.lib.prefect_runner import prefect_run_flow


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run tvscreener PipelineRunSpec via Prefect")
    parser.add_argument("--spec", required=True, help="Path to PipelineRunSpec JSON")
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts/prefect",
        help="Directory to write artifacts under (relative to repo root recommended)",
    )
    args = parser.parse_args()

    # Match the batch runner behavior: interpret relative paths from repo root so
    # reruns are stable regardless of invocation cwd.
    import os

    os.chdir(_repo_root())

    raw = Path(args.spec).read_text(encoding="utf-8")
    spec = PipelineRunSpec.model_validate_json(raw).normalized()
    result = prefect_run_flow(
        spec_payload=spec.model_dump(),
        params_hash=spec.params_hash,
        artifacts_dir=args.artifacts_dir,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
