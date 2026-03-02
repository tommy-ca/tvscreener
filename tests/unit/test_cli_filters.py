import sys

from tvscreener import cli
from tvscreener.lib import orchestrator


class DummySettings:
    default_universe = "majors"
    default_timeframes = "240,60,15"
    contract_type = "cfd"
    min_volume = None
    max_atr = None
    min_ma_score = None
    min_confluence = 2
    trend_threshold = 0.0
    mr_threshold = 0.2
    min_roc = None

    class Opportunity:
        trend_weight = 0.4
        ma_weight = 0.3
        osc_weight = 0.2
        roc_weight = 0.1
        timeframe_weights = "240:0.2,60:0.3,15:0.5"
        min_volume = None
        max_atr = None
        min_ma_score = None

    class Risk:
        min_tf_alignment = 2
        require_momentum = False
        min_rvol = 1.0
        require_volume_spike = False
        risk_per_trade_pct = 1.0
        atr_multiplier = 2.0
        min_risk_reward_ratio = 1.5
        account_balance = 10000.0

    opportunity = Opportunity()
    risk = Risk()


def test_cli_filter_args_take_precedence(monkeypatch):
    monkeypatch.setattr(orchestrator, "load_settings", lambda config: DummySettings())

    captured = {}

    def fake_run_scan(self, request):
        captured["min_confluence"] = request.scoring.min_confluence
        captured["trend_threshold"] = request.scoring.trend_threshold
        captured["mr_threshold"] = request.scoring.mr_threshold
        captured["min_roc"] = request.assets.min_roc
        return 0

    monkeypatch.setattr(orchestrator.ScreenerController, "run_scan", fake_run_scan)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tvscreener.cli",
            "--min-confluence",
            "5",
            "--trend-threshold",
            "0.5",
            "--mr-threshold",
            "0.7",
            "--min-roc",
            "0.3",
        ],
    )

    exit_code = cli.main()

    # main returns 1 if count is 0
    assert exit_code == 1
    assert captured == {
        "min_confluence": 5,
        "trend_threshold": 0.5,
        "mr_threshold": 0.7,
        "min_roc": 0.3,
    }
