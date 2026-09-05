import pandas as pd

from tvscreener_ext.orchestrator import ScreenerController


def test_load_latest_signals_latest_crypto_prefers_entity_id(monkeypatch):
    controller = ScreenerController(console=None)

    calls = []

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def query_sql(self, table, sql, params=None, snapshot_id=None):
            calls.append(sql)
            return pd.DataFrame({"entity_id": ["BINANCE:BTCUSDT"], "asset_type": ["crypto"]})

    monkeypatch.setattr("tvscreener_ext.query.EdgeQueryClient", lambda: _FakeClient())

    df = controller._workflow._load_latest_signals(
        asset_type="crypto",
        pairs=["BINANCE:BTCUSDT"],
        timeframes=["240", "60", "15"],
    )

    assert not df.empty
    assert any("entity_id IN" in s for s in calls)
