from pyiceberg.catalog import Catalog

from .manager import get_manager
from .manager import write_iceberg as write_iceberg


def get_catalog() -> Catalog:
    """Provides a singleton instance of the Iceberg catalog."""
    return get_manager().get_catalog()
