"""Factory for creating encoding paths."""

import logging
from typing import Dict, Type, Optional
from pathlib import Path

from drapto.core.base import BaseEncoder
from .chunked import ChunkedEncoder
from .dolby_vision import DolbyVisionEncoder

logger = logging.getLogger(__name__)

class EncodingPathFactory:
    """Factory for creating encoding path instances."""
    
    def __init__(self):
        """Initialize factory."""
        self._logger = logging.getLogger(__name__)
        self._paths: Dict[str, Type[BaseEncoder]] = {}
        
        # Register default paths
        self.register_path("dolby_vision", DolbyVisionEncoder)
        
    def register_path(self, name: str, path_class: Type[BaseEncoder]) -> None:
        """Register an encoding path.
        
        Args:
            name: Name of the encoding path
            path_class: Class implementing the encoding path
        """
        self._paths[name] = path_class
        self._logger.debug(f"Registered encoding path: {name}")
        
    def create_path(self, name: str, config: Dict[str, str]) -> Optional[BaseEncoder]:
        """Create an instance of an encoding path.
        
        Args:
            name: Name of the encoding path to create
            config: Configuration for the encoder
            
        Returns:
            Instance of the encoding path or None if not found
        """
        path_class = self._paths.get(name)
        if not path_class:
            self._logger.error(f"Encoding path not found: {name}")
            return None
            
        try:
            return path_class(config)
        except Exception as e:
            self._logger.error(f"Failed to create encoding path {name}: {e}")
            return None

# Global factory instance
factory = EncodingPathFactory()
