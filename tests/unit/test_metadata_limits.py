import json

from tvscreener.lib.screeners.metadata_utils import MetadataCollector


def test_metadata_api_call_limit():
    """Test that MetadataCollector correctly limits API calls and tracks dropped ones."""
    max_calls = 10
    collector = MetadataCollector(max_api_calls=max_calls)

    # Add more than the limit
    for i in range(max_calls + 5):
        collector.add_api_call(f"http://test.com/{i}", 200)

    data = collector.to_dict()
    assert len(data["api_summary"]) == max_calls
    assert data["api_summary_stats"]["recorded_count"] == max_calls
    assert data["api_summary_stats"]["dropped_count"] == 5

    # Check that it stops adding
    assert len(collector.api_calls) == max_calls
    assert collector.dropped_api_calls_count == 5


def test_metadata_to_json_truncation():
    """Test that to_json truncates when the size limit is exceeded."""
    collector = MetadataCollector(max_api_calls=1000)

    # Add some calls to have some data
    for i in range(100):
        collector.add_api_call(f"http://test.com/{i}", 200)

    # Check regular serialization
    json_str = collector.to_json()
    assert len(json_str) > 0

    # Test with a very small max_size to force truncation of api_summary
    # Each call is ~100 bytes, 100 calls = 10KB.
    # Let's set limit to 1KB.
    truncated_json = collector.to_json(max_size=1024)
    data = json.loads(truncated_json)

    assert data["api_summary"] == []
    assert data["api_summary_truncated"] is True
    assert len(truncated_json) <= 1024


def test_metadata_extreme_truncation():
    """Test that to_json truncates config if it's still too large."""
    collector = MetadataCollector()
    # Massive config
    collector.set_config({"big": "X" * 10000})

    # Try to serialize with 1KB limit
    truncated_json = collector.to_json(max_size=1024)
    data = json.loads(truncated_json)

    assert "error" in data["config"]
    assert len(truncated_json) <= 1024


def test_metadata_hard_truncation_safety():
    """Test that to_json returns valid error JSON instead of hard-truncating."""
    collector = MetadataCollector()
    # The basic structure (version, execution_stats) is ~150-200 bytes.
    # Set limit to something extremely small
    json_str = collector.to_json(max_size=50)

    # It should be valid JSON
    data = json.loads(json_str)
    assert data["error"] == "metadata_too_large"
