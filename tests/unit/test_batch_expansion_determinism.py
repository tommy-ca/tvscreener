from __future__ import annotations

import json

from workflows.prefect.run_batch import load_batch_specs


def test_load_batch_specs_is_deterministic_for_same_matrix(tmp_path):
    batch = {
        "defaults": {
            "scanner_family": "opportunity",
            "pipeline_mode": "analytics",
            "universe": "all",
        },
        "matrix": {
            "asset_types": ["forex", "stock", "crypto"],
            "universes": ["all"],
            "scanners": ["opportunity"],
            "timeframe_sets": [["15", "60", "240"], ["5", "15", "60"]],
        },
    }
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(json.dumps(batch), encoding="utf-8")

    _, specs_a, _ = load_batch_specs(str(batch_path))
    _, specs_b, _ = load_batch_specs(str(batch_path))

    hashes_a = [s.params_hash for s in specs_a]
    hashes_b = [s.params_hash for s in specs_b]

    assert hashes_a == hashes_b
    assert len(hashes_a) == 6
    assert len(set(hashes_a)) == 6


def test_load_batch_specs_multi_asset_multi_timeframe_contract(tmp_path):
    batch = {
        "defaults": {
            "scanner_family": "opportunity",
            "pipeline_mode": "analytics",
            "universe": "all",
        },
        "matrix": {
            "asset_types": ["forex", "stock", "crypto"],
            "scanners": ["opportunity"],
            "timeframe_sets": [["15", "60", "240"], ["5", "15", "60"]],
        },
    }
    batch_path = tmp_path / "batch_contract.json"
    batch_path.write_text(json.dumps(batch), encoding="utf-8")

    _, specs, _ = load_batch_specs(str(batch_path))

    assert specs
    assert {s.asset_type for s in specs} == {"forex", "stock", "crypto"}
    assert {tuple(s.timeframes) for s in specs} == {("15", "60", "240"), ("5", "15", "60")}
    assert all(s.timeframe_set_id for s in specs)
    assert all(s.scanner_family == "opportunity" for s in specs)
    assert all(s.pipeline_mode == "analytics" for s in specs)
