"""Base classes and interfaces for video encoding."""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Protocol
from pydantic import BaseModel

from drapto.monitoring import ResourceMonitor

logger = logging.getLogger(__name__)

class EncodingContext(BaseModel):
    """Context for encoding operation."""
    input_path: Path
    output_path: Path
    target_vmaf: float
    preset: int
    svt_params: str
    crop_filter: Optional[str] = None

class EncodingPath(Protocol):
    """Protocol for encoding path implementations."""
    
    async def encode_content(self, context: EncodingContext) -> bool:
        """Encode content according to context."""
        ...

class BaseEncoder:
    """Base class for video encoders."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize encoder with config."""
        self.config = config
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize resource monitor with config values or defaults
        self._monitor = ResourceMonitor(
            min_disk_gb=config.get('min_disk_gb', 10.0),
            max_cpu_percent=config.get('max_cpu_percent', 90.0),
            max_memory_percent=config.get('max_memory_percent', 90.0)
        )
    
    async def encode_content(self, context: EncodingContext) -> bool:
        """Encode content according to context."""
        raise NotImplementedError("Subclasses must implement encode_content")
    
    async def _validate_input(self, context: EncodingContext) -> bool:
        """Validate input file exists and is readable."""
        try:
            # Check system resources first
            if not self._monitor.check_resources(context.input_path.parent):
                return False
                
            if not os.path.exists(context.input_path):
                self._logger.error("Input file does not exist")
                return False
            if not os.access(context.input_path, os.R_OK):
                self._logger.error("Input file is not readable")
                return False
            return True
        except Exception as e:
            self._logger.error(f"Input validation failed: {str(e)}")
            return False
    
    async def _validate_output(self, context: EncodingContext) -> bool:
        """Validate output file exists and is valid."""
        try:
            # Check system resources first
            if not self._monitor.check_resources(context.output_path.parent):
                return False
                
            if not os.path.exists(context.output_path):
                self._logger.error("Output file does not exist")
                return False
            if os.path.getsize(context.output_path) == 0:
                self._logger.error("Output file is empty")
                return False
            return True
        except Exception as e:
            self._logger.error(f"Output validation failed: {str(e)}")
            return False
            
    def get_resources(self, path: Optional[Path] = None) -> Dict[str, float]:
        """Get current resource usage.
        
        Args:
            path: Optional path to check disk space for
            
        Returns:
            Dictionary with current resource usage percentages
        """
        resources = self._monitor.get_resources(path)
        return {
            'cpu_percent': resources.cpu_percent,
            'memory_percent': resources.memory_percent,
            'disk_percent': resources.disk_percent,
            'disk_free_gb': resources.disk_free_gb
        }
