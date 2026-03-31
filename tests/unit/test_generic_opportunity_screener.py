from tvscreener_ext.screeners.base import ScreenerConfig
from tvscreener_ext.screeners.factory import AssetScreenerFactory


def test_generic_opportunity_screener_crypto_sets_asset_type():
    screener = AssetScreenerFactory.create_screener(
        asset_type="crypto",
        symbols=["BINANCE:BTCUSDT"],
        timeframes=["15"],
        config=ScreenerConfig(),
    )

    assert screener.asset_type == "crypto"
    instance = screener._get_screener_instance()
    assert instance.__class__.__name__ == "CryptoScreener"
