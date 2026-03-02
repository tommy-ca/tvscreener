import os

import pytest


@pytest.fixture(autouse=True)
def test_mode():
    os.environ["TVSCREENER_TEST_MODE"] = "1"
    yield
    # We don't necessarily need to unset it, but it's good practice if other things depend on it
    # However, since it's autouse, it will be set for every test.
