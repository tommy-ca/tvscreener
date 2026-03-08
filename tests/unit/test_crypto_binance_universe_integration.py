from unittest.mock import patch

from tvscreener.lib.orchestrator import ScreenerController


def test_orchestrator_crypto_binance_universe_uses_selector():
    controller = ScreenerController(console=None)

    with patch(
        "tvscreener.lib.universe.binance_crypto.build_binance_crypto_universe",
        return_value=(["BINANCE:BTCUSDT"], {"count": 1, "rows": []}),
    ):
        pairs = controller.get_pairs("crypto", "binance_spot_top100", specific=None)
    assert pairs == ["BINANCE:BTCUSDT"]
