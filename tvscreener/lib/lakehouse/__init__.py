from pyiceberg.catalog import Catalog

from .catalog import IcebergCatalogManager

_catalog_manager = IcebergCatalogManager()


def get_catalog() -> Catalog:
    """Provides a singleton instance of the Iceberg catalog."""
    return _catalog_manager.get_catalog()
