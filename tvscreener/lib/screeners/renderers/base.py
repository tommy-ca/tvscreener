from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


class BaseRenderer(ABC):
    """Abstract base class for screener output renderers."""

    @abstractmethod
    def render(self, screener: Any, **kwargs: Any) -> None:
        """Render the results of a screener.

        Args:
            screener: The screener instance containing data and config.
            **kwargs: Rendering options (e.g., limit, detailed, matrix).
        """
        pass
