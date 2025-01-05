"""Base classes and interfaces for video encoding."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Protocol
import logging
import os

logger = logging.getLogger(__name__)

@dataclass
class EncodingContext:
    """Base context for encoding operations."""
    input_path: Path
    output_path: Path
    target_vmaf: float
    preset: int
    svt_params: str
    crop_filter: Optional[str] = None

class EncodingPath(Protocol):
    """Interface for encoding paths."""
    
    async def validate_input(self, context: EncodingContext) -> bool:
        """Validate input content for this path.
        
        Args:
            context: Encoding context with input parameters
            
        Returns:
            True if validation passes
        """
        ...
    
    async def encode(self, context: EncodingContext) -> bool:
        """Execute the encoding process.
        
        Args:
            context: Encoding context with input parameters
            
        Returns:
            True if encoding succeeds
        """
        ...
    
    async def validate_output(self, context: EncodingContext) -> bool:
        """Validate encoded output.
        
        Args:
            context: Encoding context with input parameters
            
        Returns:
            True if validation passes
        """
        ...

class BaseEncoder(ABC):
    """Base class for encoders."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize encoder.
        
        Args:
            config: Encoding configuration dictionary
        """
        self.config = config
        self._logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    async def encode_content(self, context: EncodingContext) -> bool:
        """Implement encoding logic.
        
        Args:
            context: Encoding context with input parameters
            
        Returns:
            True if encoding succeeds
        """
        pass
    
    async def _validate_input(self, context: EncodingContext) -> bool:
        """Validate input file and parameters.
        
        Args:
            context: Encoding context with input parameters
            
        Returns:
            True if validation passes
        """
        try:
            # Check input file exists
            if not os.path.exists(context.input_path):
                self._logger.error("Input file does not exist")
                return False
                
            # Check input file is readable
            if not os.access(context.input_path, os.R_OK):
                self._logger.error("Input file is not readable")
                return False
                
            # Check output directory exists/can be created
            output_dir = context.output_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Check output directory is writable
            if not os.access(output_dir, os.W_OK):
                self._logger.error(f"Output directory not writable: {output_dir}")
                return False
                
            return True
            
        except Exception as e:
            self._logger.error(f"Input validation failed: {str(e)}")
            return False
    
    async def _validate_output(self, context: EncodingContext) -> bool:
        """Validate encoded output file.
        
        Args:
            context: Encoding context with input parameters
            
        Returns:
            True if validation passes
        """
        try:
            # Check output file exists
            if not os.path.exists(context.output_path):
                self._logger.error("Output file does not exist")
                return False
                
            # Check output file is not empty
            if os.path.getsize(context.output_path) == 0:
                self._logger.error("Output file is empty")
                return False
                
            # TODO: Add more validation (duration, streams, etc)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Output validation failed: {str(e)}")
            return False
