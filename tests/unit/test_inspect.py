import pandas as pd

from tvscreener_ext.inspect_utils import inspect_parquet
from tvscreener_ext.screeners.metadata_utils import MetadataCollector


def test_inspect_parquet_no_file(capsys):
    inspect_parquet("non_existent.parquet")
    captured = capsys.readouterr()
    assert "Error: File not found" in captured.out


def test_inspect_parquet_with_metadata(tmp_path, capsys):
    # Create a dummy parquet file with metadata
    path = str(tmp_path / "test.parquet")
    df = pd.DataFrame({"PAIR": ["EURUSD"], "Price": [1.10]})

    import json

    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(df)
    metadata = {"version": "1.0", "config": {"test": True}}
    table = table.replace_schema_metadata({"tvscreener_metadata": json.dumps(metadata)})
    pq.write_table(table, path)

    inspect_parquet(path)
    captured = capsys.readouterr()
    assert "Embedded Metadata" in captured.out
    assert "Version: 1.0" in captured.out
    assert "test: True" in captured.out
    assert "EURUSD" in captured.out


def test_metadata_collector_json_serialization():
    collector = MetadataCollector()
    collector.set_config({"float": 1.5, "int": 10})
    collector.add_api_call("http://test.com", 200)
    collector.finish(5)

    json_str = collector.to_json()
    assert '"results_count": 5' in json_str
    assert '"status_code": 200' in json_str
    assert '"float": 1.5' in json_str


def test_metadata_collector_header_sanitization():
    collector = MetadataCollector()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "X-Request-Id": "12345",
        "X-TV-Token": "secret-token",
        "X-TV-Session-Id": "secret-session",
        "Authorization": "Bearer secret",
    }

    collector.add_api_call("https://api.tradingview.com/scan", 200, headers=headers)

    api_call = collector.api_calls[0]
    sanitized_headers = api_call["headers"]

    # Standard whitelisted headers should be present
    assert sanitized_headers["User-Agent"] == "Mozilla/5.0"
    assert sanitized_headers["Content-Type"] == "application/json"
    assert sanitized_headers["X-Request-Id"] == "12345"

    # Sensitive X-TV- and other headers should NOT be present
    assert "X-TV-Token" not in sanitized_headers
    assert "X-TV-Session-Id" not in sanitized_headers
    assert "Authorization" not in sanitized_headers
