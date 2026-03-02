from typing import Any, Protocol, runtime_checkable

import pandas as pd

from tvscreener.filter import FilterError


class FilterExecutionError(FilterError):
    """Exception raised for errors in filter execution."""

    pass


@runtime_checkable
class DataFrameFilter(Protocol):
    """
    Protocol for DataFrame filters.
    A filter must be callable, accepting a pandas DataFrame and returning one.
    """

    def __call__(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame: ...
