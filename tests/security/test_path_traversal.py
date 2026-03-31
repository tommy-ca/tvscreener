import pytest
from tvscreener_ext.orchestrator import ScreenerController
from tvscreener_ext.utils.logic import validate_path


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


def test_validate_path_symlink_escape_rejected(tmp_path):
    """Symlink that resolves outside base_dir should be rejected when tmp bypass is disabled."""
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    link = base_dir / "symlink.txt"
    link.symlink_to(secret)

    with pytest.raises(ValueError, match="Path traversal detected"):
        validate_path(str(link), base_dir=base_dir, allow_tmp=False)


def test_validate_path_tilde_rejected(tmp_path):
    """Tilde paths should be rejected as outside base_dir when not explicitly allowed."""
    with pytest.raises(ValueError, match="Path traversal detected|Invalid path"):
        validate_path("~/duckdb_test_tilde.csv", base_dir=tmp_path, allow_tmp=False)
