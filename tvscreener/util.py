import math
import os
import sys
from pathlib import Path
from typing import Any

from tvscreener.field import (
    add_historical,
    add_historical_to_label,
    add_rec,
    add_rec_to_label,
)


def to_scalar(val: Any) -> float:
    """Convert a potential Series to a float scalar."""
    if hasattr(val, "iloc"):
        return float(val.iloc[0])
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def validate_path(
    path_str: str, base_dir: Path | None = None, allow_tmp: bool | None = None
) -> Path:
    """
    Validate that a path is safe and within the allowed directory.

    :param path_str: Path string to validate
    :param base_dir: Base directory to restrict the path to (defaults to CWD)
    :param allow_tmp: Whether to allow paths in /tmp. If None, it's allowed only in test environments.
    :return: Resolved absolute Path object
    :raises ValueError: If path is invalid or outside allowed directory
    """
    if allow_tmp is None:
        # Default to True only in test environments
        allow_tmp = (
            os.getenv("TVSCREENER_TEST_MODE") == "1"
            or "pytest" in sys.modules
            or "unittest" in sys.modules
        )

    try:
        requested_path = Path(path_str).absolute()
        # Security: Resolve both paths to handle symlinks and redundant separators
        cwd = base_dir.resolve() if base_dir else Path.cwd().resolve()
        resolved_path = requested_path.resolve()
    except Exception as e:
        raise ValueError(f"Invalid path: {path_str}") from e

    # Check for path traversal or escape from allowed directory
    try:
        resolved_path.relative_to(cwd)
    except ValueError:
        # Security: Only allow /tmp bypass if explicitly enabled
        tmp_dir = Path("/tmp").resolve()
        if allow_tmp and resolved_path.is_relative_to(tmp_dir):
            return resolved_path

        raise ValueError(
            f"Path traversal detected or path outside allowed directory: {path_str}"
        ) from None

    return resolved_path


def format_historical_field(field_, historical=1):
    """
    Format the technical field to include historical offset
    :param field_: Field to format
    :param historical: Historical offset (default 1)
    :return: Formatted field name
    :raises ValueError: If field is not a historical field
    """

    # Fixed: Use proper exception instead of assert
    if not field_.historical:
        raise ValueError(f"{field_} is not a historical field")
    formatted_technical_field = add_historical(field_.field_name, historical)

    return formatted_technical_field


def get_columns_to_request(fields_):
    """
    Assemble the technical columns for the request
    :param fields_: list of fields to be requested
    :return:
    """

    # Build a dict of technical label and field label
    columns = {field.field_name: field.label for field in fields_}

    # Drop column that starts with "pattern"
    columns = {k: v for k, v in columns.items() if not k.startswith("candlestick")}

    # Add the update mode column to every request
    columns["update_mode"] = "Update Mode"

    # Format the fields that embed the time interval in the name
    columns = {_format_timed_fields(k): v for k, v in columns.items()}

    # Add the recommendation columns
    rec_columns = {
        add_rec(field.field_name): add_rec_to_label(field.field_name)
        for field in fields_
        if field.has_recommendation()
    }

    # Add the historical columns
    hist_columns = {
        format_historical_field(field): add_historical_to_label(field.label)
        for field in fields_
        if field.historical
    }

    # Merge the dicts
    columns = {**columns, **rec_columns, **hist_columns}

    return columns


def _format_timed_fields(field_):
    """Format fields that embed the time interval in the name
    e.g. 'change.1W' -> 'change|1W'"""
    # Split the field by '.'
    if (
        field_.startswith("change") or field_.startswith("relative_volume_intraday")
    ) and "." in field_:
        num = field_.split(".")[1]
        # is num a number?
        if num.isdigit() or num in ["1W", "1M"]:
            return field_.replace(".", "|")
    return field_


def is_status_code_ok(response):
    """Check if HTTP response status code indicates success."""
    return response.ok  # Simplified: use built-in ok property


def get_url(subtype):
    return f"https://scanner.tradingview.com/{subtype}/scan"


# Use proper abbreviations including K for thousands
millnames = ["", "K", "M", "B", "T"]


def millify(n):
    """
    Convert a number to abbreviated form (e.g., 1000 -> 1.000K, 1000000 -> 1.000M).

    :param n: Number to convert
    :return: String representation with abbreviation
    """
    n = float(n)
    # Handle negative numbers
    is_negative = n < 0
    n = abs(n)

    millidx = max(0, min(len(millnames) - 1, int(math.floor(0 if n == 0 else math.log10(n) / 3))))

    result = f"{n / 10 ** (3 * millidx):.3f}{millnames[millidx]}"
    return "-" + result if is_negative else result


def _is_nan(value):
    """
    Check if a value is NaN (Not a Number).

    :param value: Value to check
    :return: True if value is NaN, False otherwise
    """
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def get_recommendation(rating):
    """
    Convert a numeric rating to a recommendation string.

    :param rating: Numeric rating value
    :return: "S" (Sell) for negative, "N" (Neutral) for zero, "B" (Buy) for positive
    :raises ValueError: If rating is not a valid number
    """
    try:
        rating = float(rating)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid rating: {rating}. Rating should be a number.") from e

    if rating < 0:
        return "S"  # Sell
    elif rating == 0:
        return "N"  # Neutral
    else:  # rating > 0
        return "B"  # Buy


def parse_timeframe_weights(
    spec: str | None, default: dict[str, float] | None = None
) -> dict[str, float]:
    """
    Parse timeframe weights from a string (format 240:0.2,60:0.3,15:0.5).

    :param spec: Comma-separated string of timeframe:weight pairs
    :param default: Default weights if spec is empty or invalid
    :return: Dictionary mapping timeframe to weight
    """
    if not spec:
        return default or {}

    weights: dict[str, float] = {}
    for entry in spec.split(","):
        if not entry:
            continue
        key, sep, value = entry.partition(":")
        if sep and value:
            try:
                weights[key.strip()] = float(value.strip())
            except ValueError:
                continue
    return weights or (default or {})
