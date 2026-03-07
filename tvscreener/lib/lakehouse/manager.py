import contextlib
import logging
import re
from pathlib import Path
from typing import Any

import narwhals as nw
import pyarrow as pa
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.exceptions import NoSuchTableError

logger = logging.getLogger(__name__)


class LakehouseManager:
    """Unified manager for Iceberg catalog and storage operations.

    Flattens the previous multi-class hierarchy into a single entry point.
    """

    def __init__(self, config_path: str | None = None) -> None:
        # Config is loaded via layered Pydantic settings (ENV/.env/YAML/defaults).
        # `config_path` is the YAML path as provided to the CLI (optional).
        from tvscreener.config.loader import load_settings

        self._config_path = config_path
        self._settings = load_settings(config_path)
        self._catalog_settings = self._settings.lakehouse.catalog

        self.base_dir: Path | None = None
        self.catalog_db_path: Path | None = None
        self.warehouse_path: Path | None = None

        # Local catalog defaults/provisioning
        if self._catalog_settings.mode == "local":
            base_dir = self._settings.lakehouse_local_base_dir()
            if self._catalog_settings.local.base_dir:
                base_dir = Path(self._catalog_settings.local.base_dir).expanduser()

            self.base_dir = base_dir
            self.catalog_db_path = base_dir / self._catalog_settings.local.catalog_db
            self.warehouse_path = base_dir / self._catalog_settings.local.warehouse_dir

            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.warehouse_path.mkdir(parents=True, exist_ok=True)

        self._catalog: Catalog | None = None

    def _warehouse_uri(self) -> str:
        """Return the Iceberg warehouse URI for the configured catalog mode."""
        if self._catalog_settings.mode == "local":
            assert self.warehouse_path is not None
            return f"file://{self.warehouse_path.absolute()}"

        remote = self._catalog_settings.remote
        assert remote is not None
        warehouse = remote.warehouse
        if "://" in warehouse:
            return warehouse
        return f"file://{Path(warehouse).expanduser().absolute()}"

    def _catalog_uri(self) -> str:
        """Return the Iceberg SQL catalog URI."""
        if self._catalog_settings.mode == "local":
            assert self.catalog_db_path is not None
            return f"sqlite:////{self.catalog_db_path.absolute()}"
        remote = self._catalog_settings.remote
        assert remote is not None
        return remote.uri

    def get_catalog(self) -> Catalog:
        """Loads and returns the Iceberg catalog instance."""
        if self._catalog is None:
            props: dict[str, Any] = {
                "type": self._catalog_settings.type,
                "uri": self._catalog_uri(),
                "warehouse": self._warehouse_uri(),
                **(self._catalog_settings.properties or {}),
            }
            self._catalog = load_catalog(
                self._catalog_settings.name,
                **props,
            )
        return self._catalog

    def write_table(
        self,
        df_native: Any,
        table_name: str,
        mode: str = "append",
        partition_by: list[str] | None = None,
        overwrite_filter: Any = None,
    ) -> None:
        """Write a native dataframe to an Iceberg table with schema evolution.

        Args:
            df_native: The dataframe to write (Pandas, Polars, Arrow, etc.)
            table_name: Name of the table (e.g., 'default.bronze')
            mode: 'append' or 'overwrite'
            partition_by: Optional list of columns to partition by (creates identity partitions)
            overwrite_filter: Optional explicit Iceberg expression to filter what is overwritten.
                             If not provided and mode='overwrite' and partition_by is set,
                             it is automatically calculated from the data.
        """
        identifier = self._normalize_table_identifier(table_name)

        nw_df = nw.from_native(df_native)
        arrow_table = self._prepare_arrow(nw_df)

        catalog = self.get_catalog()

        # Ensure namespace exists
        namespace = identifier.split(".")[0]
        with contextlib.suppress(Exception):
            catalog.create_namespace(namespace)

        try:
            table = catalog.load_table(identifier)
            # Schema evolution
            with table.update_schema() as update:
                update.union_by_name(arrow_table.schema)

            if mode == "overwrite":
                if overwrite_filter is not None:
                    table.overwrite(arrow_table, overwrite_filter=overwrite_filter)
                elif partition_by:
                    from pyiceberg.expressions import AlwaysFalse, And, In, IsNull, Or

                    filters = []
                    for col in partition_by:
                        col_vals = arrow_table.column(col).to_pylist()
                        # Stable de-dupe while preserving order
                        raw_unique = list(dict.fromkeys(col_vals))
                        unique_vals = [v for v in raw_unique if v is not None]
                        has_null = None in raw_unique

                        col_filter = None
                        if unique_vals:
                            col_filter = In(col, unique_vals)  # type: ignore[call-arg,arg-type]

                        if has_null:
                            null_filter = IsNull(col)  # type: ignore[call-arg,arg-type]
                            col_filter = Or(col_filter, null_filter) if col_filter else null_filter

                        if col_filter:
                            filters.append(col_filter)

                    if not filters:
                        # Empty data + partition_by: overwrite nothing
                        table.overwrite(arrow_table, overwrite_filter=AlwaysFalse())
                    else:
                        final_filter = filters[0] if len(filters) == 1 else And(*filters)
                        table.overwrite(arrow_table, overwrite_filter=final_filter)

                else:
                    table.overwrite(arrow_table)
                logger.info("Overwrote Iceberg table '%s' (%d rows)", identifier, len(arrow_table))
            else:
                table.append(arrow_table)
                logger.info("Appended %d rows to Iceberg table '%s'", len(arrow_table), identifier)
        except NoSuchTableError:
            # Create table if it doesn't exist
            catalog.create_table(identifier, schema=arrow_table.schema)
            table = catalog.load_table(identifier)

            if partition_by:
                with table.update_spec() as update:
                    for col in partition_by:
                        update.add_identity(col)

            table.append(arrow_table)
            logger.info("Created Iceberg table '%s' (%d rows)", identifier, len(arrow_table))

    _IDENT_PART_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def _normalize_table_identifier(self, table_name: str) -> str:
        """Normalize and validate an Iceberg identifier.

        Accepts:
        - `table` (normalized to `default.table`)
        - `namespace.table`

        Rejects path traversal and path-like identifiers (e.g. containing '/', '\\\\', '..').
        """
        if table_name is None:
            raise ValueError("Invalid table identifier: None")
        raw = str(table_name).strip()
        if not raw:
            raise ValueError("Invalid table identifier: empty")
        if raw != str(table_name):
            raise ValueError(f"Invalid table identifier: '{table_name}' (whitespace not allowed)")
        if any(sep in raw for sep in ("/", "\\", ":")):
            raise ValueError(f"Invalid table identifier: '{raw}' (path separators not allowed)")
        if ".." in raw:
            raise ValueError(f"Invalid table identifier: '{raw}' ('..' not allowed)")
        if raw.startswith(".") or raw.endswith("."):
            raise ValueError(f"Invalid table identifier: '{raw}' (cannot start/end with '.')")
        if raw.count(".") > 1:
            raise ValueError(
                f"Invalid table identifier: '{raw}' (expected 'table' or 'namespace.table')"
            )

        if "." in raw:
            namespace, table = raw.split(".")
        else:
            namespace, table = "default", raw

        if not self._IDENT_PART_RE.match(namespace):
            raise ValueError(f"Invalid namespace: '{namespace}'")
        if not self._IDENT_PART_RE.match(table):
            raise ValueError(f"Invalid table name: '{table}'")
        return f"{namespace}.{table}"

    def _prepare_arrow(self, nw_df: nw.DataFrame) -> pa.Table:
        """Cast datetime columns to microseconds and strip timezones for Iceberg compatibility."""
        # Iceberg timestamps are typically timezone-naive; normalize any tz-aware datetimes to UTC
        # and drop tz info before Arrow conversion.
        try:
            import datetime as _dt

            import pandas as _pd

            native = nw_df.to_native()
            if isinstance(native, _pd.DataFrame):
                for col in list(native.columns):
                    s = native[col]
                    # datetime64[ns, tz]
                    if _pd.api.types.is_datetime64tz_dtype(s):
                        native[col] = s.dt.tz_convert("UTC").dt.tz_localize(None)
                        continue
                    # object series containing tz-aware datetimes
                    if s.dtype == "object":
                        sample = None
                        for v in s.head(50).tolist():
                            if isinstance(v, _dt.datetime):
                                sample = v
                                break
                        if sample is not None and getattr(sample, "tzinfo", None) is not None:
                            coerced = _pd.to_datetime(s, utc=True, errors="coerce")
                            native[col] = coerced.dt.tz_convert("UTC").dt.tz_localize(None)
                nw_df = nw.from_native(native)
        except Exception:
            # Best-effort normalization; continue to Arrow conversion.
            pass

        datetime_cols = [
            col for col, dtype in nw_df.schema.items() if isinstance(dtype, nw.Datetime)
        ]
        if datetime_cols:
            nw_df = nw_df.with_columns(
                [nw.col(col).cast(nw.Datetime(time_unit="us")) for col in datetime_cols]
            )
        return nw_df.to_arrow()

    def maintenance(self, table_name: str, operation: str, **kwargs: Any) -> None:
        """Perform table maintenance (expire snapshots, remove orphans)."""
        from datetime import datetime, timedelta, timezone

        from pyiceberg.table.maintenance import MaintenanceTable

        catalog = self.get_catalog()
        table = catalog.load_table(table_name)
        m = MaintenanceTable(table)

        if operation == "expire_snapshots":
            days = kwargs.get("older_than_days", 7)
            ts = datetime.now(timezone.utc) - timedelta(days=days)
            m.expire_snapshots().older_than(ts).commit()
        elif operation == "remove_orphan_files":
            m.remove_orphan_files().commit()
        elif operation == "compact":
            logger.info("Compaction requested for %s (Hook)", table_name)


_MANAGER_INSTANCE: LakehouseManager | None = None


def get_manager(config_path: str | None = None) -> LakehouseManager:
    """Singleton provider for LakehouseManager.

    If called with a config_path before the singleton is created, that YAML will be used for
    lakehouse settings. Subsequent calls ignore config_path to avoid mid-process catalog swaps.
    """
    global _MANAGER_INSTANCE
    if _MANAGER_INSTANCE is None:
        _MANAGER_INSTANCE = LakehouseManager(config_path=config_path)
    elif config_path and getattr(_MANAGER_INSTANCE, "_config_path", None) not in (
        None,
        config_path,
    ):
        logger.warning(
            "LakehouseManager already initialized with config_path=%s; ignoring new config_path=%s",
            getattr(_MANAGER_INSTANCE, "_config_path", None),
            config_path,
        )
    return _MANAGER_INSTANCE


def write_iceberg(
    df: Any,
    table_name: str,
    mode: str = "append",
    partition_by: list[str] | None = None,
    overwrite_filter: Any = None,
) -> None:
    """Legacy helper for write_iceberg."""
    get_manager().write_table(
        df, table_name, mode=mode, partition_by=partition_by, overwrite_filter=overwrite_filter
    )
