from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from tvscreener_ext.screeners.metadata_utils import MetadataEncoder
from tvscreener_ext.utils.logic import validate_path

logger = logging.getLogger(__name__)


class ExportService:
    """Service for unified artifact and metadata export."""

    def export_dataframe(
        self,
        df: pd.DataFrame,
        output_path_str: str,
        metadata: dict[str, Any],
        *,
        label: str,
        base_dir: Path | None = None,
    ) -> Path:
        """Export a dataframe to the specified path with metadata injection."""
        path = validate_path(output_path_str, base_dir=base_dir)
        self._ensure_parent_exists(path)

        fmt = path.suffix.lower().lstrip(".")
        if not fmt:
            fmt = "csv"
            path = path.with_suffix(".csv")

        logger.info("Exporting %s to %s (format=%s)", label, path, fmt)

        if fmt == "csv":
            df.to_csv(path, index=False)
        elif fmt == "json":
            self._export_json(df, path, metadata)
        elif fmt == "parquet":
            df.to_parquet(path, index=False)
        elif fmt == "xml":
            self._export_xml(df, path)
        else:
            raise ValueError(f"Unsupported export format: {fmt}")

        return path

    def _ensure_parent_exists(self, path: Path) -> None:
        """Ensure the parent directory of a path exists."""
        path.parent.mkdir(parents=True, exist_ok=True)

    def _export_json(self, df: pd.DataFrame, path: Path, metadata: dict[str, Any]) -> None:
        """Export dataframe to JSON with metadata injection."""
        payload = {
            "metadata": metadata,
            "data": df.to_dict(orient="records"),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, cls=MetadataEncoder)

    def _export_xml(self, df: pd.DataFrame, path: Path) -> None:
        """Export dataframe to XML (Legacy format)."""
        # Note: pandas.to_xml requires additional dependencies or specific versions.
        # We use a simple records-based XML for compatibility if to_xml is missing.
        try:
            df.to_xml(path, index=False)
        except (ImportError, AttributeError):
            logger.warning("pandas.to_xml not available, using fallback records XML")
            root = "root"
            xml_data = ['<?xml version="1.0" encoding="UTF-8"?>', f"<{root}>"]
            for _, row in df.iterrows():
                xml_data.append("  <record>")
                for col, val in row.items():
                    xml_data.append(f"    <{col}>{val}</{col}>")
                xml_data.append("  </record>")
            xml_data.append(f"</{root}>")
            path.write_text("\n".join(xml_data), encoding="utf-8")
