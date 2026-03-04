from pyiceberg.catalog import Catalog

from .manager import get_manager
from .manager import write_iceberg as write_iceberg


def get_catalog(config_path: str | None = None) -> Catalog:
    """Provides a singleton instance of the Iceberg catalog.

    If config_path is provided and the manager is not yet initialized, that YAML will be used to
    configure the lakehouse catalog/warehouse.
    """
    return get_manager(config_path=config_path).get_catalog()
