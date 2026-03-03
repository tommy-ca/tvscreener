from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tvscreener.lib.lakehouse.manager import LakehouseManager


@pytest.fixture
def mock_catalog():
    with patch("tvscreener.lib.lakehouse.manager.load_catalog") as mock:
        yield mock


def test_write_append_default(mock_catalog):
    storage = LakehouseManager()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    storage.write_table(df, "test_table")

    # Should call append
    mock_table.append.assert_called_once()
    mock_table.overwrite.assert_not_called()


def test_write_overwrite(mock_catalog):
    storage = LakehouseManager()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    storage.write_table(df, "test_table", mode="overwrite")

    # Should call overwrite
    mock_table.overwrite.assert_called_once()
    mock_table.append.assert_not_called()


def test_write_schema_evolution_with_overwrite(mock_catalog):
    storage = LakehouseManager()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    # Mock update_schema context manager
    mock_update = MagicMock()
    mock_table.update_schema.return_value.__enter__.return_value = mock_update

    df = pd.DataFrame({"a": [1, 2], "new_col": [10.0, 20.0]})
    storage.write_table(df, "test_table", mode="overwrite")

    # Schema evolution should be called
    mock_table.update_schema.assert_called_once()
    mock_update.union_by_name.assert_called_once()
    mock_table.overwrite.assert_called_once()


def test_write_overwrite_partition_filter(mock_catalog):
    storage = LakehouseManager()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    df = pd.DataFrame({"date": ["2026-03-01", "2026-03-02"], "value": [1, 2]})
    storage.write_table(df, "test_table", mode="overwrite", partition_by=["date"])

    # Should call overwrite with filter
    from pyiceberg.expressions import In

    mock_table.overwrite.assert_called_once()
    kwargs = mock_table.overwrite.call_args.kwargs
    assert "overwrite_filter" in kwargs
    # Filter should be In("date", ["2026-03-01", "2026-03-02"])
    f = kwargs["overwrite_filter"]
    assert isinstance(f, In)
    assert f.term.name == "date"
    assert f.literals == In("date", ["2026-03-01", "2026-03-02"]).literals


def test_write_overwrite_multi_partition_filter(mock_catalog):
    storage = LakehouseManager()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    df = pd.DataFrame(
        {"asset": ["stock", "crypto"], "date": ["2026-03-01", "2026-03-02"], "value": [1, 2]}
    )
    storage.write_table(df, "test_table", mode="overwrite", partition_by=["asset", "date"])

    # Should call overwrite with And filter
    from pyiceberg.expressions import And, In

    mock_table.overwrite.assert_called_once()
    kwargs = mock_table.overwrite.call_args.kwargs
    assert "overwrite_filter" in kwargs
    f = kwargs["overwrite_filter"]
    assert isinstance(f, And)
    # Check that both asset and date filters are present
    assert any(isinstance(sub, In) and sub.term.name == "asset" for sub in [f.left, f.right])
    assert any(isinstance(sub, In) and sub.term.name == "date" for sub in [f.left, f.right])


def test_write_explicit_overwrite_filter(mock_catalog):
    storage = LakehouseManager()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    from pyiceberg.expressions import EqualTo

    custom_filter = EqualTo("some_col", "some_val")
    df = pd.DataFrame({"some_col": ["some_val"], "value": [1]})
    storage.write_table(df, "test_table", mode="overwrite", overwrite_filter=custom_filter)

    mock_table.overwrite.assert_called_once()
    kwargs = mock_table.overwrite.call_args.kwargs
    assert kwargs["overwrite_filter"] == custom_filter
