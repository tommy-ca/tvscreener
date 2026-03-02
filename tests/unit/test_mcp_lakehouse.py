from unittest.mock import MagicMock, patch

import pytest

from tvscreener.mcp.tools import lakehouse_get_schema, lakehouse_list_tables, lakehouse_maintenance


@pytest.fixture
def mock_catalog():
    with patch("tvscreener.mcp.tools.get_catalog") as mock:
        catalog = MagicMock()
        mock.return_value = catalog
        yield catalog


def test_lakehouse_list_tables_success(mock_catalog):
    mock_catalog.list_namespaces.return_value = [("tvscreener",)]
    mock_catalog.list_tables.return_value = [("tvscreener", "bronze"), ("tvscreener", "silver")]

    result = lakehouse_list_tables()

    assert "tvscreener.bronze" in result
    assert "tvscreener.silver" in result
    mock_catalog.list_namespaces.assert_called_once()
    mock_catalog.list_tables.assert_called_with(("tvscreener",))


def test_lakehouse_list_tables_empty(mock_catalog):
    mock_catalog.list_namespaces.return_value = []

    result = lakehouse_list_tables()

    assert "No tables found" in result


def test_lakehouse_get_schema_success(mock_catalog):
    mock_table = MagicMock()
    # Mocking pyiceberg schema structure roughly
    mock_field = MagicMock()
    mock_field.name = "symbol"
    mock_field.field_type = "string"
    mock_field.required = True

    mock_table.schema().fields = [mock_field]
    mock_catalog.load_table.return_value = mock_table

    result = lakehouse_get_schema("tvscreener.bronze")

    assert "symbol" in result
    assert "string" in result
    mock_catalog.load_table.assert_called_with("tvscreener.bronze")


def test_lakehouse_get_schema_not_found(mock_catalog):
    from pyiceberg.exceptions import NoSuchTableError

    mock_catalog.load_table.side_effect = NoSuchTableError("No table")

    result = lakehouse_get_schema("invalid.table")

    assert "Error" in result
    assert "not found" in result


def test_lakehouse_maintenance_expire_snapshots(mock_catalog):
    mock_table = MagicMock()
    mock_catalog.load_table.return_value = mock_table

    with patch("pyiceberg.table.maintenance.MaintenanceTable") as mock_mt:
        result = lakehouse_maintenance("tvscreener.bronze", "expire_snapshots", older_than_days=7)

        assert "Successfully executed expire_snapshots" in result
        mock_mt.assert_called_once_with(mock_table)


def test_lakehouse_maintenance_remove_orphan_files(mock_catalog):
    mock_table = MagicMock()
    mock_catalog.load_table.return_value = mock_table

    with patch("pyiceberg.table.maintenance.MaintenanceTable") as mock_mt:
        result = lakehouse_maintenance("tvscreener.bronze", "remove_orphan_files")

        assert "Successfully executed remove_orphan_files" in result
        mock_mt.assert_called_once_with(mock_table)


def test_lakehouse_maintenance_invalid_operation(mock_catalog):
    result = lakehouse_maintenance("tvscreener.bronze", "invalid_op")
    assert "Unsupported maintenance operation" in result
