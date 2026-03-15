from tvscreener.constants.market_risk import (
    MARKET_RISK_FUTURES_TICKERS,
    MARKET_RISK_PROXY_TICKERS,
)
from tvscreener.lib.orchestrator import ScreenerController


def test_market_risk_universe_resolves_stock_proxies() -> None:
    controller = ScreenerController(console=None)
    out = controller.get_pairs("stock", "market_risk", specific=None)
    assert out == MARKET_RISK_PROXY_TICKERS


def test_market_risk_universe_resolves_futures_basket() -> None:
    controller = ScreenerController(console=None)
    out = controller.get_pairs("futures", "market_risk", specific=None)
    assert out == MARKET_RISK_FUTURES_TICKERS
