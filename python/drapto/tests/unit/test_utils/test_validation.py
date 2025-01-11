"""Tests for input validation utilities."""

import os
import pytest
from pathlib import Path

from drapto.utils.validation import validate_input_file


@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file."""
    file_path = tmp_path / "test.txt"
    file_path.touch()
    return file_path


def test_validate_input_file_exists(test_file):
    """Test validation of existing file."""
    result = validate_input_file(test_file)
    assert isinstance(result, Path)
    assert result == test_file


def test_validate_input_file_str_path(test_file):
    """Test validation with string path."""
    result = validate_input_file(str(test_file))
    assert isinstance(result, Path)
    assert result == test_file


def test_validate_input_file_not_found():
    """Test validation of non-existent file."""
    with pytest.raises(FileNotFoundError) as exc_info:
        validate_input_file("/nonexistent/file.txt")
    assert "does not exist" in str(exc_info.value)


def test_validate_input_file_is_dir(tmp_path):
    """Test validation when path is a directory."""
    with pytest.raises(ValueError) as exc_info:
        validate_input_file(tmp_path)
    assert "not a file" in str(exc_info.value)


def test_validate_input_file_not_readable(test_file):
    """Test validation of non-readable file."""
    os.chmod(test_file, 0o000)  # Remove all permissions
    try:
        with pytest.raises(PermissionError) as exc_info:
            validate_input_file(test_file)
        assert "not readable" in str(exc_info.value)
    finally:
        os.chmod(test_file, 0o666)  # Restore permissions
