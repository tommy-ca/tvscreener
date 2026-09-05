from __future__ import annotations

from typing import Any, cast

from . import runner as pipeline_runner
from .enums import Direction
from .lakehouse import LakehouseManager, get_manager
from .models import (
    AssetSelection,
    OutputConfig,
    RiskConfig,
    ScanRequest,
    ScoringConfig,
)
from .orchestrator import ScreenerController
from .prefect import run_batch as prefect_runner
from .runner import LocalRunner, PipelineRunSpec
from .scoring import ScoringConfig as ScoringWeights
from .scoring import ScoringEngine
from .upstream import ensure_upstream_tvscreener

# --- Monkeypatch tvscreener for test compatibility ---


def _patch_field():
    from tvscreener.field import Field

    try:
        from tvscreener.field import FieldWithInterval
    except ImportError:
        FieldWithInterval = cast(Any, None)
    try:
        from tvscreener.field import FieldWithHistory
    except ImportError:
        FieldWithHistory = cast(Any, None)

    from .screeners.filters import FieldCondition, FilterOperator

    def __gt__(self, other):
        return FieldCondition(self, FilterOperator.ABOVE, other)

    def __ge__(self, other):
        return FieldCondition(self, FilterOperator.ABOVE_OR_EQUAL, other)

    def __lt__(self, other):
        return FieldCondition(self, FilterOperator.BELOW, other)

    def __le__(self, other):
        return FieldCondition(self, FilterOperator.BELOW_OR_EQUAL, other)

    def __eq__(self, other):
        types = tuple(filter(None, [Field, FieldWithInterval, FieldWithHistory]))
        if isinstance(other, types):
            return self is other or getattr(self, "field_name", str(self)) == getattr(
                other, "field_name", str(other)
            )
        return FieldCondition(self, FilterOperator.EQUAL, other)

    def __ne__(self, other):
        types = tuple(filter(None, [Field, FieldWithInterval, FieldWithHistory]))
        if isinstance(other, types):
            return not (self == other)
        return FieldCondition(self, FilterOperator.NOT_EQUAL, other)

    def between(self, min_val, max_val):
        return FieldCondition(self, FilterOperator.IN_RANGE, [min_val, max_val])

    def not_between(self, min_val, max_val):
        return FieldCondition(self, FilterOperator.NOT_IN_RANGE, [min_val, max_val])

    def isin(self, values):
        return FieldCondition(self, FilterOperator.IN_RANGE, values)

    def not_in(self, values):
        return FieldCondition(self, FilterOperator.NOT_IN_RANGE, values)

    for cls in filter(None, [Field, FieldWithInterval, FieldWithHistory]):
        cls.__gt__ = __gt__  # ty: ignore
        cls.__ge__ = __ge__  # ty: ignore
        cls.__lt__ = __lt__  # ty: ignore
        cls.__le__ = __le__  # ty: ignore
        cls.__eq__ = __eq__  # ty: ignore
        cls.__ne__ = __ne__  # ty: ignore
        cls.between = between  # ty: ignore
        cls.not_between = not_between  # ty: ignore
        cls.isin = isin  # ty: ignore
        cls.not_in = not_in  # ty: ignore


def _patch_screeners():
    from tvscreener import CryptoScreener, ForexScreener, StockScreener

    def set_tickers(self, *tickers):
        tks = [t.upper() for t in tickers]
        self.symbols = {"tickers": tks}
        if hasattr(self, "add_misc"):
            self.add_misc("symbols", {"tickers": tks})

    def set_symbols(self, *symbols):
        tks = [s.upper() for s in symbols]
        self.symbols = {"tickers": tks}
        if hasattr(self, "add_misc"):
            self.add_misc("symbols", {"tickers": tks})

    for cls in (StockScreener, CryptoScreener, ForexScreener):
        cls.set_tickers = set_tickers  # ty: ignore
        cls.set_symbols = set_symbols  # ty: ignore


def _patch_where():
    from tvscreener.core.base import Screener

    original_where = Screener.where

    def where(self, condition_or_field, operation=None, value=None):
        if hasattr(condition_or_field, "to_filter"):
            f = condition_or_field.to_filter()
            self.filters.append(f)
            return self
        return original_where(self, condition_or_field, cast(Any, operation), value)

    Screener.where = where  # ty: ignore


def _patch_get():
    import requests
    import tvscreener.util
    from tvscreener.core.base import Screener, ScreenerDataFrame
    from tvscreener.exceptions import MalformedRequestException

    def get(self, print_request=False):
        if self.range == [0, 150] and self.symbols and "tickers" in self.symbols:
            end = len(self.symbols["tickers"])
            self.range = [0, max(150, end)]

        columns = tvscreener.util.get_columns_to_request(self.specific_fields)
        payload = self._build_payload(list(columns.keys()))
        import json

        payload_json = json.dumps(payload, indent=4)

        if print_request:
            print(f"Request: {self.url}")
            print("Payload:")
            print(payload_json)

        response = requests.post(self.url, data=payload_json, timeout=30)

        if not tvscreener.util.is_status_code_ok(response):
            raise MalformedRequestException(
                response.status_code, response.text, self.url, payload_json
            )

        res_json = response.json()
        if "data" not in res_json:
            raise MalformedRequestException(
                response.status_code, "missing 'data' key", self.url, payload_json
            )

        data_list = res_json["data"]
        if not isinstance(data_list, list):
            raise MalformedRequestException(
                response.status_code, "data should be a list", self.url, payload_json
            )

        expected_len = len(columns) + 1
        rows = []
        for d in data_list:
            if not isinstance(d, dict) or "s" not in d or "d" not in d:
                raise MalformedRequestException(
                    response.status_code, "missing data 's' or 'd' key", self.url, payload_json
                )
            row = [d["s"]] + d["d"]
            if len(row) != expected_len:
                raise MalformedRequestException(
                    response.status_code,
                    f"Data length mismatch. Expected {expected_len}, got {len(row)}",
                    self.url,
                    payload_json,
                )
            rows.append(row)

        return ScreenerDataFrame(rows, columns)

    Screener.get = get  # ty: ignore


def _patch_range():
    from tvscreener.core.base import Screener

    def set_range(self, start=0, end=None):
        if end is None:
            if self.symbols and "tickers" in self.symbols:
                end = len(self.symbols["tickers"])
            else:
                end = 150
        self.range = [start, end]
        return self

    Screener.set_range = set_range  # ty: ignore


_patch_field()
_patch_screeners()
_patch_where()
_patch_get()
_patch_range()

__all__ = [
    "AssetSelection",
    "OutputConfig",
    "RiskConfig",
    "ScanRequest",
    "ScoringConfig",
    "ScoringWeights",
    "Direction",
    "LakehouseManager",
    "get_manager",
    "ScreenerController",
    "LocalRunner",
    "PipelineRunSpec",
    "ScoringEngine",
    "ensure_upstream_tvscreener",
    "pipeline_runner",
    "prefect_runner",
]
