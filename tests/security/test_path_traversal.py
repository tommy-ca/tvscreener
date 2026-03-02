import pytest

from tvscreener.lib.orchestrator import ScreenerController


@pytest.fixture()
def controller():
    return ScreenerController()


def test_validate_path_traversal_absolute(controller):
    """Absolute path outside CWD should raise ValueError."""
    with pytest.raises(ValueError, match="Path traversal detected"):
        controller._validate_path("/etc/passwd")


def test_validate_path_traversal_relative(controller):
    """Relative path escaping CWD via .. should raise ValueError."""
    with pytest.raises(ValueError, match="Path traversal detected"):
        controller._validate_path("../traversal_test.yaml")


def test_validate_path_legitimate(controller, tmp_path):
    """Legitimate path within the base directory should succeed."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("test: data")

    result = controller._validate_path(str(config_file), base_dir=tmp_path)
    assert result == config_file.resolve()


def test_validate_path_legitimate_nested(controller, tmp_path):
    """Nested legitimate path within the base directory should succeed."""
    nested = tmp_path / "subdir"
    nested.mkdir()
    config_file = nested / "config.yaml"
    config_file.write_text("test: data")

    result = controller._validate_path(str(config_file), base_dir=tmp_path)
    assert result == config_file.resolve()
