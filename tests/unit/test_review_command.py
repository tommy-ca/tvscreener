import json
from pathlib import Path
from unittest.mock import MagicMock

from tvscreener.lib.orchestrator import ScreenerController


def test_review_runs_audit_then_report(tmp_path: Path):
    controller = ScreenerController(console=None)
    controller.run_audit = MagicMock(return_value=0)
    controller.run_report = MagicMock(return_value=0)

    args = type(
        "Args",
        (),
        {
            "command": "review",
            "target": "binance-universes",
            "audit_out_dir": str(tmp_path / "audits"),
            "report_out_dir": str(tmp_path / "reports"),
            "strict": False,
            "verbose": False,
            "config": None,
        },
    )()

    assert controller.run_review(args) == 0
    assert controller.run_audit.call_count == 1
    assert controller.run_report.call_count == 1


def test_review_strict_fails_when_audit_has_errors(tmp_path: Path):
    controller = ScreenerController(console=None)

    def _write_audit(_args):
        out_dir = Path(_args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(
            json.dumps({"universes": {"binance_spot_top100": {"errors": ["underfilled_top_n"]}}}),
            encoding="utf-8",
        )
        return 0

    controller.run_audit = MagicMock(side_effect=_write_audit)
    controller.run_report = MagicMock(return_value=0)

    args = type(
        "Args",
        (),
        {
            "command": "review",
            "target": "binance-universes",
            "audit_out_dir": str(tmp_path / "audits"),
            "report_out_dir": str(tmp_path / "reports"),
            "strict": True,
            "verbose": False,
            "config": None,
        },
    )()

    assert controller.run_review(args) == 2
    assert controller.run_report.call_count == 0
