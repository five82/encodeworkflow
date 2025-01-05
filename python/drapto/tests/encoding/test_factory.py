"""Tests for encoding path factory."""

import pytest
import pytest_asyncio
from unittest.mock import Mock

from drapto.encoding.factory import EncodingPathFactory, factory
from drapto.encoding.base import BaseEncoder

@pytest.fixture
def mock_encoder_class():
    """Create mock encoder class."""
    class MockEncoder(BaseEncoder):
        async def encode_content(self, context):
            return True
            
    return MockEncoder

@pytest.mark.asyncio
class TestEncodingPathFactory:
    """Test EncodingPathFactory implementation."""
    
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, mock_encoder_class):
        """Set up test cases."""
        self.factory = EncodingPathFactory()
        self.mock_encoder = mock_encoder_class
        
        yield
    
    async def test_register_path(self):
        """Test registering an encoding path."""
        self.factory.register_path("test_path", self.mock_encoder)
        assert "test_path" in self.factory._paths
        assert self.factory._paths["test_path"] == self.mock_encoder
    
    async def test_create_path_success(self):
        """Test creating a registered path."""
        self.factory.register_path("test_path", self.mock_encoder)
        encoder = self.factory.create_path("test_path", {"test": "config"})
        
        assert encoder is not None
        assert isinstance(encoder, self.mock_encoder)
    
    async def test_create_path_not_found(self):
        """Test creating an unregistered path."""
        encoder = self.factory.create_path("missing_path", {"test": "config"})
        assert encoder is None
    
    async def test_create_path_error(self):
        """Test creating a path that raises an error."""
        # Create mock encoder that raises an error
        class ErrorEncoder(BaseEncoder):
            def __init__(self, config):
                raise ValueError("Test error")
                
            async def encode_content(self, context):
                return True
                
        self.factory.register_path("error_path", ErrorEncoder)
        encoder = self.factory.create_path("error_path", {"test": "config"})
        assert encoder is None
    
    async def test_global_factory(self):
        """Test the global factory instance."""
        assert isinstance(factory, EncodingPathFactory)
        
        # Register a path in the global factory
        factory.register_path("global_test", self.mock_encoder)
        encoder = factory.create_path("global_test", {"test": "config"})
        
        assert encoder is not None
        assert isinstance(encoder, self.mock_encoder)
