"""Common test fixtures for encoding tests."""

import pytest
import pytest_asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock

from drapto.core.base import BaseEncoder

@pytest_asyncio.fixture
async def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def test_config():
    """Create test configuration."""
    return {
        "target_vmaf": 93.0,
        "preset": 6,
        "svt_params": "film-grain=0:film-grain-denoise=0",
        "vmaf_sample_count": 3,
        "vmaf_sample_length": 1
    }

@pytest.fixture
def mock_encoder_class():
    """Create a mock encoder class."""
    class MockEncoder(BaseEncoder):
        async def encode_content(self, context):
            return True
            
    return MockEncoder
