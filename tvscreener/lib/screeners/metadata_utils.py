import json
import threading
from datetime import datetime
from typing import Any

import numpy as np


class MetadataEncoder(json.JSONEncoder):
    """Custom JSON encoder for types not supported by default."""

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


class MetadataCollector:
    """Collects scan metadata and API summaries for audit trails."""

    # Strictly whitelisted headers that are safe to export
    HEADER_WHITELIST = {
        "User-Agent",
        "Content-Type",
        "X-Request-Id",
        "Server-Timing",
        "Date",
    }

    def __init__(self, version: str = "1.0", max_api_calls: int = 100):
        self.version = version
        self.max_api_calls = max_api_calls
        self.start_time = datetime.now()
        self.end_time: datetime | None = None
        self.config: dict[str, Any] = {}
        self.api_calls: list[dict[str, Any]] = []
        self.dropped_api_calls_count = 0
        self.summary_stats: dict[str, Any] = {}
        self._lock = threading.Lock()

    def set_config(self, config_dict: dict[str, Any]) -> None:
        """Set the scanner configuration."""
        with self._lock:
            self.config = config_dict

    def update_config(self, config_dict: dict[str, Any]) -> None:
        """Update the scanner configuration."""
        with self._lock:
            self.config.update(config_dict)

    def add_api_call(
        self,
        url: str,
        status_code: int,
        method: str = "POST",
        headers: dict[str, str] | None = None,
    ) -> None:
        """Add a sanitized summary of an API call."""
        sanitized_headers = {}
        if headers:
            sanitized_headers = {k: v for k, v in headers.items() if k in self.HEADER_WHITELIST}

        with self._lock:
            if len(self.api_calls) < self.max_api_calls:
                self.api_calls.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "url": url,
                        "method": method,
                        "status_code": status_code,
                        "headers": sanitized_headers,
                    }
                )
            else:
                self.dropped_api_calls_count += 1

    def finish(self, results_count: int, **extra_stats) -> None:
        """Mark the scan as finished and record summary statistics."""
        with self._lock:
            self.end_time = datetime.now()
            self.summary_stats = {"results_count": results_count, **extra_stats}

    def to_dict(self) -> dict[str, Any]:
        """Convert all collected metadata to a dictionary."""
        with self._lock:
            duration = None
            if self.end_time:
                duration = (self.end_time - self.start_time).total_seconds()

            return {
                "version": self.version,
                "execution_stats": {
                    "start_time": self.start_time.isoformat(),
                    "end_time": self.end_time.isoformat() if self.end_time else None,
                    "duration_seconds": duration,
                },
                "config": self.config,
                "summary_stats": self.summary_stats,
                "api_summary": list(self.api_calls),
                "api_summary_stats": {
                    "recorded_count": len(self.api_calls),
                    "dropped_count": self.dropped_api_calls_count,
                },
            }

    def to_json(self, max_size: int = 10 * 1024 * 1024) -> str:
        """Serialize metadata to a JSON string with size safety.

        Args:
            max_size: Maximum size of the resulting JSON string in bytes (default 10MB).
        """
        data = self.to_dict()
        serialized = json.dumps(data, cls=MetadataEncoder)

        # If it exceeds the limit, try to truncate it.
        if len(serialized) > max_size:
            # 1. First, try clearing API calls
            data["api_summary"] = []
            data["api_summary_truncated"] = True
            serialized = json.dumps(data, cls=MetadataEncoder)

            # 2. If it's still too large (extreme case: massive config), we must truncate more.
            if len(serialized) > max_size:
                # Remove config
                data["config"] = {"error": "Config too large, truncated"}
                serialized = json.dumps(data, cls=MetadataEncoder)

            # 3. Final safety: return a valid JSON error object if it's still too large
            # (though with config and api calls cleared, it should be very small).
            if len(serialized) > max_size:
                return json.dumps({"error": "metadata_too_large"})

        return serialized
