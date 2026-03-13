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


def test_orchestrator_crypto_binance_universe_aliases_route_correctly():
    controller = ScreenerController(console=None)

    with patch(
        "tvscreener.lib.universe.binance_crypto.build_binance_crypto_universe_tradeable_base",
        return_value=(["BINANCE:BTCUSDT"], {"count": 1, "rows": []}),
    ):
        pairs = controller.get_pairs("crypto", "binance_spot_base", specific=None)
    assert pairs == ["BINANCE:BTCUSDT"]

    with patch(
        "tvscreener.lib.universe.binance_crypto.build_binance_crypto_universe_tradeable_mcap_overlap",
        return_value=(["BINANCE:ETHUSDT"], {"count": 1, "rows": []}),
    ):
        pairs = controller.get_pairs("crypto", "binance_spot_largecap", specific=None)
    assert pairs == ["BINANCE:ETHUSDT"]


def test_orchestrator_crypto_majors_minors_keywords_route_by_instrument_type():
    controller = ScreenerController(console=None)

    with patch(
        "tvscreener.lib.universe.binance_crypto.build_binance_crypto_universe_mcap_tier",
        return_value=(["BINANCE:BTCUSDT"], {"count": 1, "rows": []}),
    ):
        pairs = controller.get_pairs("crypto", "majors", specific=None, instrument_type="spot")
    assert pairs == ["BINANCE:BTCUSDT"]

    with patch(
        "tvscreener.lib.universe.binance_crypto.build_binance_crypto_universe_mcap_tier",
        return_value=(["BINANCE:ETHUSDT.P"], {"count": 1, "rows": []}),
    ):
        pairs = controller.get_pairs("crypto", "minors", specific=None, instrument_type="perp")
    assert pairs == ["BINANCE:ETHUSDT.P"]
