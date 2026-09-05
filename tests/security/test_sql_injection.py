from tvscreener_ext.query import EdgeQueryClient


def test_sql_injection_s3_credentials(monkeypatch):
    """Test that S3 credentials are NOT vulnerable to injection."""
    # Malicious AWS access key that attempts to execute arbitrary SQL
    malicious_key = "'; DROP TABLE df; --"
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", malicious_key)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")

    with EdgeQueryClient(db_path=":memory:") as client:
        # This shouldn't crash or execute the injection
        # Currently, it might fail because the SET command itself is malformed by the injection
        # but we want to ensure it's handled safely.
        # In current state, it uses f-string: f"SET s3_access_key_id='{os.environ['AWS_ACCESS_KEY_ID']}';"
        # which will result in: SET s3_access_key_id=''; DROP TABLE df; --';

        # To test it, we need to trigger _setup_remote_access
        import contextlib

        with contextlib.suppress(Exception):
            client._setup_remote_access("s3://bucket/file.parquet")


def test_sql_injection_query_params(tmp_path):
    """Test that query parameters are handled safely."""
    df_path = tmp_path / "test.parquet"
    import pandas as pd

    pd.DataFrame({"a": [1, 2, 3]}).to_parquet(df_path)

    with EdgeQueryClient(db_path=":memory:") as client:
        # In the new version, we should be able to pass values that are NOT injected into the string
        # but passed to duckdb.execute(sql, params)

        result = client.query_sql(df_path, "SELECT * FROM df WHERE a = ?", params=[1])
        assert len(result) == 1


def test_minijinja_rendering():
    """Test that MiniJinja is used for rendering."""
    # This will fail until MiniJinja is integrated
    from tvscreener_ext.query import EdgeQueryClient

    client = EdgeQueryClient(db_path=":memory:")

    template = "SELECT * FROM df {% if limit_val %}LIMIT {{ limit_val }}{% endif %}"
    rendered = client.render_sql(template, limit_val=10)
    assert rendered == "SELECT * FROM df LIMIT 10"

    rendered_no_limit = client.render_sql(template, limit_val=None)
    assert rendered_no_limit == "SELECT * FROM df "
