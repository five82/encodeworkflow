"""Tests for base encoding components."""

import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import Mock
import tempfile
import os

from drapto.encoding.base import EncodingContext, BaseEncoder

@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    if temp_dir and os.path.exists(temp_dir):
        for f in Path(temp_dir).glob("*"):
            f.unlink()
        os.rmdir(temp_dir)

@pytest.fixture
def mock_encoder_class():
    """Create a mock encoder."""
    class MockEncoder(BaseEncoder):
        async def encode_content(self, context):
            return True
    return MockEncoder

class TestEncodingContext:
    """Test EncodingContext dataclass."""
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, temp_dir):
        """Set up test cases."""
        self.temp_dir = temp_dir
        self.input_path = self.temp_dir / "input.mp4"
        self.output_path = self.temp_dir / "output.mp4"
        
        # Create dummy input file
        self.input_path.touch()
        
        yield
    
    def test_context_creation(self):
        """Test creating encoding context."""
        context = EncodingContext(
            input_path=self.input_path,
            output_path=self.output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        assert context.input_path == self.input_path
        assert context.output_path == self.output_path
        assert context.target_vmaf == 93.0
        assert context.preset == 6
        assert context.svt_params == "film-grain=0:film-grain-denoise=0"
        assert context.crop_filter is None

@pytest.mark.asyncio
class TestBaseEncoder:
    """Test BaseEncoder implementation."""
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, temp_dir, mock_encoder_class):
        """Set up test cases."""
        self.temp_dir = temp_dir
        self.input_path = self.temp_dir / "input.mp4"
        self.output_path = self.temp_dir / "output.mp4"
        
        # Create dummy input file
        self.input_path.touch()
        
        # Create test encoder
        self.encoder = mock_encoder_class({"test": "config"})
        
        yield
    
    async def test_validate_input_file_exists(self):
        """Test input validation with existing file."""
        context = EncodingContext(
            input_path=self.input_path,
            output_path=self.output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await self.encoder._validate_input(context)
        assert result is True
    
    async def test_validate_input_file_missing(self):
        """Test input validation with missing file."""
        context = EncodingContext(
            input_path=Path(self.temp_dir) / "missing.mp4",
            output_path=self.output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await self.encoder._validate_input(context)
        assert result is False
    
    async def test_validate_output_success(self):
        """Test output validation with valid file."""
        # Create dummy output file
        self.output_path.touch()
        with open(self.output_path, "wb") as f:
            f.write(b"dummy content")
            
        context = EncodingContext(
            input_path=self.input_path,
            output_path=self.output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await self.encoder._validate_output(context)
        assert result is True
    
    async def test_validate_output_empty_file(self):
        """Test output validation with empty file."""
        # Create empty output file
        self.output_path.touch()
            
        context = EncodingContext(
            input_path=self.input_path,
            output_path=self.output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await self.encoder._validate_output(context)
        assert result is False
