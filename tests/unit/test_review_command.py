from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

from tvscreener_ext.orchestrator import ScreenerController


def test_review_runs_audit_then_report(tmp_path: Path):
    controller = ScreenerController(console=None)
    controller.run_audit = MagicMock(return_value=0)  # ty: ignore
    controller.run_report = MagicMock(return_value=0)  # ty: ignore

    args = type(
        "Args",
        (),
        {
            "command": "review",
            "target": "binance-universes",
            "out_dir": str(tmp_path),
            "include_all": False,
            "verbose": False,
            "config": None,
        },
    )()

    assert controller.run_review(cast(argparse.Namespace, args)) == 0
    assert cast(MagicMock, controller.run_audit).call_count == 1
    assert cast(MagicMock, controller.run_report).call_count == 1


def test_review_stops_if_audit_fails(tmp_path: Path):
    controller = ScreenerController(console=None)
    controller.run_audit = MagicMock(return_value=2)  # ty: ignore
    controller.run_report = MagicMock(return_value=0)  # ty: ignore

    args = type(
        "Args",
        (),
        {
            "command": "review",
            "target": "binance-universes",
            "out_dir": str(tmp_path),
            "include_all": False,
            "verbose": False,
            "config": None,
        },
    )()

    assert controller.run_review(cast(argparse.Namespace, args)) == 2
    assert cast(MagicMock, controller.run_report).call_count == 0
