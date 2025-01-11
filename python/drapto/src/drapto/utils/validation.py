"""Input validation utilities."""

import os
from pathlib import Path
from typing import Union


def validate_input_file(path: Union[str, Path]) -> Path:
    """Validate that a file exists and is readable.
    
    Args:
        path: Path to file to validate
        
    Returns:
        Path object for the file
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If path is not a file
        PermissionError: If file is not readable
    """
    if isinstance(path, str):
        path = Path(path)
        
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")
        
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")
        
    if not os.access(path, os.R_OK):
        raise PermissionError(f"File is not readable: {path}")
        
    return path
