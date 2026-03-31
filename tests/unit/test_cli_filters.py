import sys

from tvscreener_ext import orchestrator
from tvscreener_ext import scan as cli


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
            "--runner",
            "local",
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


def test_cli_defaults_to_prefect_runner(monkeypatch):
    called = {}

    def fake_run_prefect(spec, *, artifacts_dir):
        called["runner"] = "prefect"
        called["scanner_family"] = spec.scanner_family
        called["pipeline_mode"] = spec.pipeline_mode
        called["asset_type"] = spec.asset_type
        called["artifacts_dir"] = artifacts_dir
        return {}

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tvscreener.cli",
            "--scanner",
            "opportunity",
            "--pipeline",
            "analytics",
            "--asset-type",
            "forex",
            "--pairs",
            "EURUSD",
        ],
    )

    from tvscreener_ext import prefect_runner

    monkeypatch.setattr(prefect_runner, "run_prefect", fake_run_prefect)

    exit_code = cli.main()

    assert exit_code == 0
    assert called == {
        "runner": "prefect",
        "scanner_family": "opportunity",
        "pipeline_mode": "analytics",
        "asset_type": "forex",
        "artifacts_dir": "artifacts/runs",
    }
