import json
from pathlib import Path

from tvscreener_ext.reports.binance_universes import generate_binance_universes_report


def test_binance_universe_report_writes_json(tmp_path: Path):
    in_dir = tmp_path / "audits"
    (in_dir / "binance_spot_tradeable_base").mkdir(parents=True)
    (in_dir / "binance_spot_tradeable_base" / "universe.json").write_text(
        json.dumps(
            {
                "constraints": {
                    "selection": "tradeable_base",
                    "instrument_type": "spot",
                },
                "count": 2,
                "rows": [
                    {
                        "ticker": "BINANCE:BTCUSDT",
                        "quote_volume_usd": 100.0,
                        "volatility_24h_pct": 4.0,
                        "instrument_type": "spot",
                        "base": "BTC",
                        "quote_asset": "USDT",
                    },
                    {
                        "ticker": "BINANCE:ETHUSDT",
                        "quote_volume_usd": 50.0,
                        "volatility_24h_pct": 5.0,
                        "instrument_type": "spot",
                        "base": "ETH",
                        "quote_asset": "USDT",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "reports"
    paths = generate_binance_universes_report(in_dir=in_dir, out_dir=out_dir, stamp="test")
    payload = json.loads(paths.report_json.read_text(encoding="utf-8"))
    assert "summary" in payload
    assert "top100_diagnostics" in payload
    assert "volume_percentiles" in payload
    assert "volume_top_assets" in payload
    assert "ticker_volumes" in payload
    assert "base_volumes" in payload
    assert "volume_bins" in payload
    assert "risky_assets" in payload
    assert "spot_quote_breakdown" in payload
    assert "strategy_readiness" in payload
    assert "scanner_readiness" in payload
    assert "spot_top100_quote_overview" in payload
    assert "spot_perp_parity" in payload
    assert payload["summary"][0]["ticker_count"] == 2
