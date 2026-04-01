from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("mcp")


@pytest.fixture
def mock_catalog():
    with patch("tvscreener.mcp.tools.get_catalog") as mock:
        yield mock
