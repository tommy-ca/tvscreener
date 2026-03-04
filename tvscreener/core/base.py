import json
import random
import time
from collections.abc import Callable, Iterator
from enum import Enum
from typing import Any

import pandas as pd
import requests

from tvscreener.exceptions import MalformedRequestException
from tvscreener.field import Field, IndexSymbol, Market
from tvscreener.field.crypto import CryptoField
from tvscreener.field.forex import ForexField
from tvscreener.field.stock import StockField
from tvscreener.filter import ExtraFilter, Filter, FilterOperator
from tvscreener.util import get_columns_to_request, is_status_code_ok

# Configuration constants
DEFAULT_MARKET = Market.AMERICA
DEFAULT_MIN_RANGE = 0
DEFAULT_MAX_RANGE = 150
DEFAULT_SORT_STOCKS = StockField.MARKET_CAPITALIZATION
DEFAULT_SORT_CRYPTO = CryptoField.VOLUME_24H_IN_USD
DEFAULT_SORT_FOREX = ForexField.NAME
REQUEST_TIMEOUT = 30  # seconds
MIN_STREAM_INTERVAL = 1.0  # minimum interval for streaming to avoid rate limiting

# HTTP headers for TradingView API requests
REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://www.tradingview.com",
    "Referer": "https://www.tradingview.com/",
}

# Backward compatibility aliases
default_market = DEFAULT_MARKET
default_min_range = DEFAULT_MIN_RANGE
default_max_range = DEFAULT_MAX_RANGE
default_sort_stocks = DEFAULT_SORT_STOCKS
default_sort_crypto = DEFAULT_SORT_CRYPTO
default_sort_forex = DEFAULT_SORT_FOREX


class ScreenerDataFrame(pd.DataFrame):
    def __init__(self, data, columns: dict, *args, **kwargs):
        # Add the extra received columns
        columns = {"symbol": "Symbol", **columns}
        super().__init__(data, *args, columns=list(columns.values()), **kwargs)

        # Reorder columns - only include first_columns that exist in the request
        first_columns = ["symbol", "name", "description"]
        ordered_columns = {k: columns.get(k) for k in first_columns if k in columns}
        ordered_columns.update({k: v for k, v in columns.items() if k not in first_columns})
        self.attrs["original_columns"] = ordered_columns
        self._update_inplace(self[ordered_columns.values()])

    def set_technical_columns(self, only: bool = False):
        if only:
            self.columns = pd.Index(self.attrs["original_columns"].keys())
        else:
            self.columns = pd.MultiIndex.from_tuples(self.attrs["original_columns"].items())


class Screener:
    """Base screener class for querying TradingView screeners."""

    # Subclasses should override this to enable field type validation
    _field_type: type[Enum] | None = None

    def __init__(self):
        self.sort: dict[str, Any] | None = None
        self.url: str = ""
        self.filters: list[Filter] = []
        self.options: dict[str, Any] = {}
        self.symbols: list[str] | None = None
        self.misc: dict[str, Any] = {}
        self.specific_fields: list[Field] | None = None

        self.range: list[int] | None = None
        self.set_range()
        self.add_option("lang", "en")

    # def add_prebuilt_filter(self, filter_: Filter):
    #    self.filters.append(filter_.to_dict())

    # def add_filter(self, filter_: Filter, operation: FilterOperator = None, values=None):
    #    filter_val = {"left": filter_, "operation": operation.value, "right": values}
    #    self.filters.append(filter_val)

    def search(self, value: str):
        self.add_filter(ExtraFilter.SEARCH, FilterOperator.MATCH, value)

    def _get_filter(self, filter_type: Field | ExtraFilter) -> Filter | None:
        for filter_ in self.filters:
            if filter_.field == filter_type:
                return filter_

    def remove_filter(self, filter_type: ExtraFilter | Field):
        filter_ = self._get_filter(filter_type)
        if filter_:
            self.filters.remove(filter_)

    @staticmethod
    def _merge_filters(current_filter: Filter, new_filter: Filter):
        if not set(new_filter.values).issubset(set(current_filter.values)):
            # Set the operation is IN_RANGE with multiple values
            current_filter.operation = FilterOperator.IN_RANGE
            current_filter.values.extend(new_filter.values)
        return current_filter

    def _add_new_filter(self, filter_: Filter):
        # Case where the filter does not exist
        # If the filter contains values array with only one value, we can use EQUAL instead of IN_RANGE
        if len(filter_.values) == 1 and filter_.operation == FilterOperator.IN_RANGE:
            filter_.operation = FilterOperator.EQUAL
        self.filters.append(filter_)

    def _validate_field_type(self, field: Field | ExtraFilter):
        """Validate that the field type matches the screener's expected field type."""
        from tvscreener.field import FieldWithHistory, FieldWithInterval

        # Skip validation for ExtraFilter (search, etc.)
        if isinstance(field, ExtraFilter):
            return
        # Skip validation if no field type is set
        if self._field_type is None:
            return
        # Handle FieldWithInterval and FieldWithHistory - check their underlying field
        if isinstance(field, (FieldWithInterval, FieldWithHistory)):
            underlying_field = field.field
            if not isinstance(underlying_field, self._field_type):
                raise TypeError(
                    f"Invalid field type: expected {self._field_type.__name__}, "
                    f"got {type(underlying_field).__name__}. "
                    f"Use {self._field_type.__name__} fields with {type(self).__name__}."
                )
            return
        # Validate field type
        if not isinstance(field, self._field_type):
            raise TypeError(
                f"Invalid field type: expected {self._field_type.__name__}, "
                f"got {type(field).__name__}. "
                f"Use {self._field_type.__name__} fields with {type(self).__name__}."
            )

    def add_filter(
        self, filter_type: Field | ExtraFilter, operation: FilterOperator, values: Enum | str
    ):
        self._validate_field_type(filter_type)
        filter_ = Filter(filter_type, operation, values)
        # Case where the filter already exists, and we want to add more values
        existing_filter = self._get_filter(filter_.field)
        if existing_filter:
            self._merge_filters(existing_filter, filter_)
        else:
            self._add_new_filter(filter_)

    def where(
        self, condition_or_field, operation: FilterOperator | None = None, value=None
    ) -> "Screener":
        """
        Add a filter condition (fluent method).

        Supports two syntaxes:

        1. **New Pythonic syntax** (recommended):
            >>> ss.where(StockField.PRICE > 100)
            >>> ss.where(StockField.VOLUME >= 1_000_000)
            >>> ss.where(StockField.MARKET_CAPITALIZATION.between(1e9, 10e9))

        2. **Legacy syntax** (still supported):
            >>> ss.where(StockField.PRICE, FilterOperator.ABOVE, 100)

        :param condition_or_field: Either a FieldCondition (from comparison) or a Field
        :param operation: Filter operation (only for legacy syntax)
        :param value: Value to compare against (only for legacy syntax)
        :return: self for method chaining

        Example:
            >>> ss = StockScreener()
            >>> # New syntax
            >>> ss.where(StockField.PRICE > 100).where(StockField.VOLUME > 1e6)
            >>> # Legacy syntax
            >>> ss.where(StockField.PRICE, FilterOperator.ABOVE, 100)
        """
        from tvscreener.filter import FieldCondition

        if isinstance(condition_or_field, FieldCondition):
            # New Pythonic syntax: ss.where(StockField.PRICE > 100)
            self.add_filter(
                condition_or_field.field, condition_or_field.operation, condition_or_field.value
            )
        else:
            # Legacy syntax: ss.where(field, operator, value)
            if operation is None:
                raise ValueError("Legacy where() requires an operation")
            if value is None:
                raise ValueError("Legacy where() requires a value")
            self.add_filter(condition_or_field, operation, value)
        return self

    def select(self, *fields: Field) -> "Screener":
        """
        Set fields to retrieve (fluent method).

        :param fields: Fields to include in results
        :return: self for method chaining

        Example:
            >>> ss = StockScreener()
            >>> ss.select(StockField.NAME, StockField.PRICE, StockField.VOLUME)
        """
        self.specific_fields = list(fields)
        return self

    def select_all(self) -> "Screener":
        """
        Select all available fields for this screener type.

        :return: self for method chaining

        Example:
            >>> ss = StockScreener()
            >>> ss.select_all()
            >>> df = ss.get()  # Returns all ~3000+ stock fields
        """
        if self._field_type is None:
            raise ValueError("Cannot select all fields: screener has no field type defined")
        self.specific_fields = list(self._field_type)
        return self

    def add_option(self, key, value):
        self.options[key] = value

    def add_misc(self, key, value):
        self.misc[key] = value

    def set_range(
        self, from_range: int = default_min_range, to_range: int = default_max_range
    ) -> "Screener":
        self.range = [from_range, to_range]
        return self

    def sort_by(self, sort_by: Field, ascending=True):
        self.sort = {"sortBy": sort_by.field_name, "sortOrder": "asc" if ascending else "desc"}

    def set_index(self, *indices: IndexSymbol) -> "Screener":
        """
        Filter screener results to only include constituents of the specified index(es).

        :param indices: One or more IndexSymbol enum values
        :return: self for method chaining

        Example:
            >>> ss = StockScreener()
            >>> ss.set_index(IndexSymbol.SP500)
            >>> df = ss.get()  # Returns only S&P 500 constituents

            >>> # Multiple indices
            >>> ss.set_index(IndexSymbol.SP500, IndexSymbol.NASDAQ_100)
        """
        if not indices:
            return self

        symbolset = [idx.symbolset_value for idx in indices]

        if self.symbols is None:
            self.symbols = {"symbolset": symbolset}
        else:
            # Merge with existing symbols configuration
            self.symbols["symbolset"] = symbolset

        return self

    def set_tickers(self, *tickers: str) -> "Screener":
        """
        Filter screener results to only include specified ticker(s).
        Tickers should be in the format 'EXCHANGE:SYMBOL'.

        :param tickers: One or more ticker symbols
        :return: self for method chaining

        Example:
            >>> ss = StockScreener()
            >>> ss.set_tickers("NASDAQ:AAPL", "NASDAQ:MSFT")
            >>> df = ss.get()
        """
        if not tickers:
            return self

        if self.symbols is None:
            self.symbols = {"tickers": list(tickers)}
        else:
            self.symbols["tickers"] = list(tickers)

        return self

    def _build_payload(self, requested_columns_):
        # Resolve symbols: merge self.symbols (from set_tickers/set_index) with
        # any misc["symbols"] (e.g. query types set by subclass constructors).
        # This prevents **self.misc from silently overwriting set_tickers().
        misc_symbols = self.misc.pop("symbols", None)

        if self.symbols is not None:
            # User explicitly set tickers/index — use that as the base
            symbols = dict(self.symbols)
            # Merge query/types from misc so subclass type filters still apply
            if misc_symbols and "query" in misc_symbols and "query" not in symbols:
                symbols["query"] = misc_symbols["query"]
        elif misc_symbols:
            # No user-set symbols — use whatever the subclass put in misc
            symbols = misc_symbols
        else:
            symbols = {"query": {"types": []}, "tickers": []}

        payload = {
            "filter": [f.to_dict() for f in self.filters],
            "options": self.options,
            "symbols": symbols,
            "sort": self.sort,
            "range": self.range,
            "columns": requested_columns_,
            **self.misc,
        }

        # Restore misc so repeated calls work correctly
        if misc_symbols is not None:
            self.misc["symbols"] = misc_symbols

        return payload

    def _validate_api_response(self, resp_json: dict, payload_json: str, status_code: int):
        """
        Validate the structure of the TradingView API response.

        :param resp_json: The response JSON to validate
        :param payload_json: The original request payload (for error reporting)
        :param status_code: The HTTP status code
        :raises MalformedRequestException: If the response is malformed
        """
        if not isinstance(resp_json, dict):
            raise MalformedRequestException(
                status_code,
                f"Invalid JSON response: expected dict, got {type(resp_json).__name__}",
                self.url,
                payload_json,
            )

        if "data" not in resp_json:
            raise MalformedRequestException(
                status_code,
                "Invalid API response: missing 'data' key",
                self.url,
                payload_json,
            )

        if not isinstance(resp_json["data"], list):
            raise MalformedRequestException(
                status_code,
                f"Invalid API response: 'data' should be a list, got {type(resp_json['data']).__name__}",
                self.url,
                payload_json,
            )

        # Validate each item in data
        for i, item in enumerate(resp_json["data"]):
            if not isinstance(item, dict):
                raise MalformedRequestException(
                    status_code,
                    f"Invalid data item at index {i}: expected dict, got {type(item).__name__}",
                    self.url,
                    payload_json,
                )

            if "s" not in item:
                raise MalformedRequestException(
                    status_code,
                    f"Invalid data item at index {i}: missing symbol 's' key",
                    self.url,
                    payload_json,
                )

            if "d" not in item:
                raise MalformedRequestException(
                    status_code,
                    f"Invalid data item at index {i}: missing data 'd' key",
                    self.url,
                    payload_json,
                )

            if not isinstance(item["d"], list):
                raise MalformedRequestException(
                    status_code,
                    f"Invalid data item at index {i}: 'd' should be a list, got {type(item['d']).__name__}",
                    self.url,
                    payload_json,
                )

    def get(self, print_request=False):
        """
        Get the screener data from TradingView.

        :param print_request: If True, prints the request URL and payload for debugging.
        :return: ScreenerDataFrame containing the screener results
        :raises MalformedRequestException: If the API request fails
        :raises requests.RequestException: If there's a network error
        """
        # Build columns
        columns = get_columns_to_request(self.specific_fields)

        payload = self._build_payload(list(columns.keys()))
        payload_json = json.dumps(payload, indent=4)

        if print_request:
            print(f"Request: {self.url}")
            print("Payload:")
            print(payload_json)

        retryable_statuses = {408, 425, 429, 500, 502, 503, 504}
        max_retries = 3
        base_backoff = 0.5

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    self.url, data=payload_json, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS
                )

                if is_status_code_ok(response):
                    try:
                        resp_json = response.json()
                        self._validate_api_response(resp_json, payload_json, response.status_code)

                        # Extract data from validated response
                        data = []
                        expected_len = len(columns)
                        for i, item in enumerate(resp_json["data"]):
                            symbol = item["s"]
                            values = item["d"]

                            if len(values) != expected_len:
                                raise MalformedRequestException(
                                    response.status_code,
                                    f"Data length mismatch at index {i}: expected {expected_len} values, got {len(values)}",
                                    self.url,
                                    payload_json,
                                )
                            data.append([symbol] + values)

                    except (ValueError, KeyError, TypeError) as e:
                        raise MalformedRequestException(
                            response.status_code,
                            f"Failed to parse API response: {str(e)}",
                            self.url,
                            payload_json,
                        ) from e

                    df = ScreenerDataFrame(data, columns)
                    safe_headers = {
                        "Content-Type",
                        "Date",
                        "Server",
                        "User-Agent",
                        "X-Request-Id",
                        "Retry-After",
                    }
                    sanitized_headers = {
                        k: v for k, v in response.headers.items() if k in safe_headers
                    }
                    df.attrs["api_context"] = {
                        "url": self.url,
                        "status_code": response.status_code,
                        "headers": sanitized_headers,
                        "method": "POST",
                    }
                    return df

                # Non-OK response
                if response.status_code in retryable_statuses and attempt < max_retries:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and str(retry_after).strip().isdigit():
                        sleep_s = min(float(retry_after), 30.0)
                    else:
                        # Exponential backoff with jitter
                        sleep_s = min(base_backoff * (2**attempt), 10.0)
                        sleep_s = sleep_s * (0.8 + 0.4 * random.random())
                    time.sleep(sleep_s)
                    continue

                raise MalformedRequestException(
                    response.status_code, response.text, self.url, payload_json
                )

            except requests.Timeout as e:
                last_exc = e
                if attempt < max_retries:
                    sleep_s = min(base_backoff * (2**attempt), 10.0)
                    sleep_s = sleep_s * (0.8 + 0.4 * random.random())
                    time.sleep(sleep_s)
                    continue
                raise MalformedRequestException(
                    408,
                    f"Request timed out after {REQUEST_TIMEOUT} seconds",
                    self.url,
                    payload_json,
                ) from e
            except requests.RequestException as e:
                last_exc = e
                if attempt < max_retries:
                    sleep_s = min(base_backoff * (2**attempt), 10.0)
                    sleep_s = sleep_s * (0.8 + 0.4 * random.random())
                    time.sleep(sleep_s)
                    continue
                raise MalformedRequestException(
                    0,
                    str(e),
                    self.url,
                    payload_json,
                ) from e

        # Should never reach here
        if last_exc:
            raise MalformedRequestException(0, str(last_exc), self.url, payload_json) from last_exc
        raise MalformedRequestException(0, "Unknown error", self.url, payload_json)

    def stream(
        self,
        interval: float = 5.0,
        max_iterations: int | None = None,
        on_update: Callable[["ScreenerDataFrame"], None] | None = None,
    ) -> Iterator["ScreenerDataFrame" | None]:
        """
        Stream screener data at regular intervals.

        :param interval: Refresh interval in seconds (minimum 1.0 to avoid rate limiting)
        :param max_iterations: Maximum number of refreshes (None = infinite)
        :param on_update: Optional callback function called with each DataFrame
        :yield: ScreenerDataFrame on each refresh, or None if an error occurs

        Example:
            >>> ss = StockScreener()
            >>> for df in ss.stream(interval=10, max_iterations=5):
            ...     print(f"Updated: {len(df)} rows")
        """
        # Enforce minimum interval to be respectful of TradingView's API
        interval = max(interval, MIN_STREAM_INTERVAL)

        iteration = 0
        while max_iterations is None or iteration < max_iterations:
            try:
                df = self.get()
                if on_update:
                    on_update(df)
                yield df
            except Exception as e:
                # Log error but continue streaming
                print(f"Error fetching data: {e}")
                yield None

            iteration += 1
            if max_iterations is None or iteration < max_iterations:
                time.sleep(interval)
