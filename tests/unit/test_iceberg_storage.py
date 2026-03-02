from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from pyiceberg.exceptions import NoSuchTableError

from tvscreener.lib.lakehouse.storage import IcebergStorage


@pytest.fixture
def mock_catalog():
    with patch("tvscreener.lib.lakehouse.storage.get_catalog") as mock:
        yield mock


def test_write_append_default(mock_catalog):
    storage = IcebergStorage()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    storage.write(df, "test_table")

    # Should call append
    mock_table.append.assert_called_once()
    mock_table.overwrite.assert_not_called()


def test_write_overwrite(mock_catalog):
    storage = IcebergStorage()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    storage.write(df, "test_table", mode="overwrite")

    # Should call overwrite
    mock_table.overwrite.assert_called_once()
    mock_table.append.assert_not_called()


def test_write_schema_evolution_with_overwrite(mock_catalog):
    storage = IcebergStorage()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.return_value = mock_table

    # Mock update_schema context manager
    mock_update = MagicMock()
    mock_table.update_schema.return_value.__enter__.return_value = mock_update

    df = pd.DataFrame({"a": [1, 2], "new_col": [10.0, 20.0]})
    storage.write(df, "test_table", mode="overwrite")

    # Schema evolution should be called
    mock_table.update_schema.assert_called_once()
    mock_update.union_by_name.assert_called_once()
    mock_table.overwrite.assert_called_once()


def test_write_creates_partitioned_table(mock_catalog):
    storage = IcebergStorage()
    mock_table = MagicMock()
    mock_catalog.return_value.load_table.side_effect = [
        NoSuchTableError("Table not found"),
        mock_table,
    ]

    # Mock update_spec
    mock_update = MagicMock()
    mock_table.update_spec.return_value.__enter__.return_value = mock_update

    df = pd.DataFrame({"date": ["2026-03-01", "2026-03-02"], "value": [1, 2]})
    storage.write(df, "partitioned_table", partition_by=["date"])

    mock_catalog.return_value.create_table.assert_called_once()
    mock_table.update_spec.assert_called_once()
    mock_update.add_identity_field.assert_called_with("date")
    mock_table.append.assert_called_once()
