from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

from tvscreener.lib.screeners.metadata_utils import MetadataEncoder


def export_to_csv(
    df_getter: Callable[[], pd.DataFrame],
    path: str,
    include_index: bool,
    *,
    logger: logging.Logger,
    label: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    df = df_getter()
    with open(path, "w", newline="") as fh:
        if metadata:
            for key, value in metadata.items():
                # Sanitize value to prevent injection via newlines (Issue 047)
                safe_value = str(value).replace("\n", " ").replace("\r", " ")
                fh.write(f"# {key}: {safe_value}\n")
        df.to_csv(fh, index=include_index)
    logger.info("Saved %d %s to %s", len(df), label, path)
    if metadata:
        _write_metadata_file(path, metadata, logger, label)


def export_to_json(
    df_getter: Callable[[], pd.DataFrame],
    path: str,
    orient: str,
    *,
    logger: logging.Logger,
    label: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    df = df_getter()
    payload: dict[str, Any] = {"data": df.to_dict(orient=orient)}
    if metadata:
        payload["metadata"] = metadata
    with open(path, "w") as fh:
        # Use MetadataEncoder to handle numpy/datetime objects (Issue 046)
        json.dump(payload, fh, indent=2, cls=MetadataEncoder)
    logger.info("Saved %d %s to %s", len(df), label, path)


def print_summary(
    df_getter: Callable[[], pd.DataFrame],
    *,
    empty_rich_message: str,
    render_rich: Callable[[pd.DataFrame, Any, Any], None],
) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        df = df_getter()
        print(df.to_string())
        return

    console = Console()
    df = df_getter()

    if df.empty:
        console.print(f"[yellow]{empty_rich_message}[/yellow]")
        return

    render_rich(df, console, Table)


def export_to_parquet(
    df_getter: Callable[[], pd.DataFrame],
    path: str,
    include_index: bool,
    *,
    logger: logging.Logger,
    label: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    df = df_getter()

    embedding_success = False
    if metadata:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            # Convert to table
            table = pa.Table.from_pandas(df, preserve_index=include_index)

            # Add metadata
            existing_meta = table.schema.metadata or {}
            json_meta = json.dumps(metadata, cls=MetadataEncoder)
            new_meta = {
                **{
                    k.decode("utf-8") if isinstance(k, bytes) else k: v
                    for k, v in existing_meta.items()
                },
                "tvscreener_metadata": json_meta,
            }

            table = table.replace_schema_metadata(new_meta)

            # Write with embedded metadata
            pq.write_table(table, path)
            embedding_success = True
            logger.info("Saved %d %s with embedded metadata to %s", len(df), label, path)
        except ImportError:
            logger.warning("pyarrow not installed. Falling back to sidecar metadata file.")
        except Exception as e:
            logger.error("Failed to embed metadata in Parquet: %s. Falling back to sidecar.", e)

    if not embedding_success:
        df.to_parquet(path, index=include_index)
        logger.info("Saved %d %s to %s", len(df), label, path)
        if metadata:
            _write_metadata_file(path, metadata, logger, label)


def export_to_xml(
    df_getter: Callable[[], pd.DataFrame],
    path: str,
    include_index: bool,
    *,
    logger: logging.Logger,
    label: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    df = df_getter()

    root = ET.Element("root")

    if metadata:
        meta_elem = ET.SubElement(root, "metadata")
        _dict_to_xml(meta_elem, metadata)

    # Get XML as string to avoid encoding issues with file handles
    xml_data = df.to_xml(index=include_index, parser="etree", xml_declaration=False)
    df_root = ET.fromstring(xml_data)
    root.append(df_root)

    tree = ET.ElementTree(root)
    tree.write(path, encoding="utf-8", xml_declaration=True)

    logger.info("Saved %d %s to %s", len(df), label, path)
    if metadata:
        _write_metadata_file(path, metadata, logger, label)


def export_to_iceberg(
    df_getter: Callable[[], pd.DataFrame],
    path: str,
    *,
    logger: logging.Logger,
    label: str,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    from pathlib import Path

    from tvscreener.lib.lakehouse import write_iceberg

    df = df_getter()
    if df.empty:
        logger.info("No %s to export to Iceberg.", label)
        return

    # Use the stem of the path as the table name
    table_name = Path(path).stem

    write_iceberg(df, table_name)
    logger.info("Saved %d %s to Iceberg table '%s'", len(df), label, table_name)


def _dict_to_xml(parent: ET.Element, data: dict[str, Any]) -> None:
    """Recursively convert dictionary to XML elements."""
    for key, value in data.items():
        # Sanitize key for XML tag safety
        safe_key = "".join(c for c in str(key) if c.isalnum() or c == "_")
        if not safe_key or not safe_key[0].isalpha():
            safe_key = f"meta_{safe_key}"

        child = ET.SubElement(parent, safe_key)
        if isinstance(value, dict):
            _dict_to_xml(child, value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                ET.SubElement(child, "item").text = str(item)
        else:
            child.text = str(value)


EXPORT_FUNCTIONS: dict[str, Callable[..., None]] = {
    "csv": export_to_csv,
    "json": export_to_json,
    "parquet": export_to_parquet,
    "xml": export_to_xml,
    "iceberg": export_to_iceberg,
}


def get_export_function(format_name: str) -> Callable[..., None]:
    exporter = EXPORT_FUNCTIONS.get(format_name.lower())
    if exporter is None:
        raise ValueError(
            f"Unknown export format '{format_name}'. Supported formats: csv, json, parquet, xml, iceberg."
        )
    return exporter


def _write_metadata_file(
    path: str, metadata: dict[str, Any], logger: logging.Logger, label: str
) -> None:
    meta_path = f"{path}.meta.json"
    with open(meta_path, "w") as fh:
        # Use MetadataEncoder to handle numpy/datetime objects (Issue 046)
        json.dump({"metadata": metadata}, fh, indent=2, cls=MetadataEncoder)
    logger.info("Saved metadata for %s to %s", label, meta_path)
