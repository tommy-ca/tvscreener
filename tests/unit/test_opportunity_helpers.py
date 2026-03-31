import logging

import pandas as pd
import yaml
from tvscreener_ext.constants.forex import DEFAULT_TIMEFRAME_WEIGHTS
from tvscreener_ext.orchestrator import (
    AssetSelection,
    ScanRequest,
    ScoringConfig,
    ScreenerController,
)
from tvscreener_ext.screeners.export_helpers import export_to_csv, export_to_json


def test_parse_timeframe_weights_valid_string():
    controller = ScreenerController()
    spec = "240:0.5,60:0.3,15:0.2"
    weights = controller._parse_timeframe_weights(spec)
    assert weights == {"240": 0.5, "60": 0.3, "15": 0.2}


def test_parse_timeframe_weights_defaults_empty():
    controller = ScreenerController()
    weights = controller._parse_timeframe_weights("")
    assert weights == DEFAULT_TIMEFRAME_WEIGHTS


def test_scan_request_defaults():
    request = ScanRequest()
    assert request.assets.scanner == "strategy"
    assert request.assets.asset_type == "forex"
    assert request.assets.min_volume is None


def test_scan_request_payload_mapping():
    request = ScanRequest(
        assets=AssetSelection(
            min_volume=100,
            max_atr=0.01,
            min_ma_score=0.5,
            include_atr=True,
            include_rsi=False,
            contract_type="cfd",
            timeframes="240,60,15",
        ),
        scoring=ScoringConfig(
            opportunity_trend_weight=0.4,
        ),
    )
    assert request.assets.min_volume == 100
    assert request.scoring.opportunity_trend_weight == 0.4
    assert request.assets.contract_type == "cfd"


def test_maybe_save_opportunity_config(tmp_path):
    controller = ScreenerController()
    path = tmp_path / "cfg" / "config.yaml"
    request = ScanRequest(assets=AssetSelection(min_volume=100, scanner="opportunity"))
    controller._maybe_save_opportunity_config(str(path), request)
    data = yaml.safe_load(path.read_text())
    assert data["min_volume"] == 100


def test_export_helpers_include_metadata(tmp_path):
    df = pd.DataFrame({"a": [1, 2]})
    csv_path = tmp_path / "out.csv"
    metadata = {"foo": "bar"}
    export_to_csv(
        lambda: df,
        str(csv_path),
        include_index=False,
        logger=logging.getLogger("test"),
        label="test",
        metadata=metadata,
    )
    with open(csv_path) as fh:
        # Check if any line starts with metadata comment
        lines = fh.readlines()
        found = any(line.strip().startswith("# foo: bar") for line in lines)
    assert found

    json_path = tmp_path / "out.json"
    export_to_json(
        lambda: df,
        str(json_path),
        orient="records",
        logger=logging.getLogger("test"),
        label="test",
        metadata={"bar": "baz"},
    )
    payload = yaml.safe_load(json_path.read_text())
    assert "metadata" in payload and payload["metadata"]["bar"] == "baz"
