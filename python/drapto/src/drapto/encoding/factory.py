"""Factory for creating encoding path instances."""

import logging
from typing import Dict, Any, Optional, Type

from .base import EncodingPath, BaseEncoder

logger = logging.getLogger(__name__)

class EncodingPathFactory:
    """Factory for creating encoding path instances."""
    
    def __init__(self):
        """Initialize factory."""
        self._logger = logging.getLogger(__name__)
        self._paths: Dict[str, Type[BaseEncoder]] = {}
        
    def register_path(self, name: str, path_class: Type[BaseEncoder]):
        """Register an encoding path.
        
        Args:
            name: Name of the encoding path
            path_class: Class implementing the encoding path
        """
        self._paths[name] = path_class
        self._logger.debug(f"Registered encoding path: {name}")
        
    def create_path(
        self,
        name: str,
        config: Dict[str, Any]
    ) -> Optional[BaseEncoder]:
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
