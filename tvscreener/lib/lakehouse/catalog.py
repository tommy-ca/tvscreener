import logging
import time
from pathlib import Path

from pyiceberg.catalog import Catalog, load_catalog

logger = logging.getLogger(__name__)


class IcebergCatalogManager:
    """Manages the lifecycle of the local Apache Iceberg catalog."""

    def __init__(self) -> None:
        self.base_dir = Path.home() / ".tvscreener" / "lakehouse"
        self.catalog_db_path = self.base_dir / "catalog.db"
        self.warehouse_path = self.base_dir / "warehouse"

        # Provision directories
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.warehouse_path.mkdir(parents=True, exist_ok=True)

        # SQL Catalog URI: sqlite:////abs/path/to/db
        self.uri = f"sqlite:////{self.catalog_db_path.absolute()}"
        self._catalog: Catalog | None = None

    def get_catalog(self) -> Catalog:
        """Loads and returns the Iceberg catalog instance."""
        if self._catalog is None:
            self._catalog = load_catalog(
                "local",
                **{
                    "type": "sql",
                    "uri": self.uri,
                    "warehouse": f"file://{self.warehouse_path.absolute()}",
                },
            )
        return self._catalog

    def expire_snapshots(self, table_name: str, older_than_days: int) -> None:
        """Expire snapshots older than a specific date to reclaim disk space."""
        catalog = self.get_catalog()
        table = catalog.load_table(table_name)

        older_than_ms = int((time.time() - (older_than_days * 86400)) * 1000)
        table.expire_snapshots(older_than_ms=older_than_ms)

    def compact_files(self, table_name: str) -> None:
        """
        Trigger file compaction for a table.
        Note: PyIceberg currently focuses on read/write; full compaction
        (rewriting data files) is typically handled by Spark or Flink engines.
        This method serves as a hook for future native compaction support.
        """
        # In a real Spark environment, this would be:
        # spark.sql(f"CALL local.system.rewrite_data_files(table => '{table_name}')")
        # For now, we just log the intent as PyIceberg 0.6.x doesn't expose a direct compact() API yet.
        logger.info(f"Maintenance: Compaction requested for {table_name} (Hook)")
