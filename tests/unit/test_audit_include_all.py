import json
from pathlib import Path

from tvscreener_ext.orchestrator import ScreenerController


def test_audit_defaults_to_screener_universes(tmp_path: Path):
    controller = ScreenerController(console=None)
    args = type(
        "Args",
        (),
        {
            "command": "audit",
            "target": "binance-universes",
            "out_dir": str(tmp_path),
            "include_all": False,
            "verbose": False,
            "config": None,
        },
    )()

    # Just verify the output list; don't assert counts.
    assert controller.run_audit(args) == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    universes = set((payload or {}).get("universes", {}).keys())
    assert "binance_spot_tradeable_base" in universes
    assert "binance_spot_majors" in universes
    assert "binance_spot_mcap_top100" not in universes


def test_audit_include_all_adds_diagnostic_universes(tmp_path: Path):
    controller = ScreenerController(console=None)
    args = type(
        "Args",
        (),
        {
            "command": "audit",
            "target": "binance-universes",
            "out_dir": str(tmp_path),
            "include_all": True,
            "verbose": False,
            "config": None,
        },
    )()

    assert controller.run_audit(args) == 0
    payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    universes = set((payload or {}).get("universes", {}).keys())
    assert "binance_spot_mcap_top100" in universes
    assert "binance_spot_cs_momentum" in universes
