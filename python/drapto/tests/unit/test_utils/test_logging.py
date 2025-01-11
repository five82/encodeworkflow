"""Tests for logging utilities."""

import logging
import pytest

from drapto.utils.logging import get_logger


def test_get_logger_name():
    """Test logger name is set correctly."""
    logger = get_logger("test.logger")
    assert logger.name == "test.logger"


def test_get_logger_level():
    """Test logger level is set correctly."""
    logger = get_logger("test.logger", level=logging.DEBUG)
    assert logger.level == logging.DEBUG


def test_get_logger_formatter():
    """Test logger formatter is configured."""
    logger = get_logger("test.logger")
    assert logger.handlers
    handler = logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.formatter is not None


def test_get_logger_singleton():
    """Test same logger is returned for same name."""
    logger1 = get_logger("test.logger")
    logger2 = get_logger("test.logger")
    assert logger1 is logger2


def test_get_logger_different_names():
    """Test different loggers for different names."""
    logger1 = get_logger("test.logger1")
    logger2 = get_logger("test.logger2")
    assert logger1 is not logger2
