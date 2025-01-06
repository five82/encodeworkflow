"""Configuration module for encoding settings."""

import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict

from loguru import logger
from pydantic import BaseModel, Field, ConfigDict

from . import default_config as defaults


class EncodingConfig(BaseModel):
    """Configuration for video encoding."""
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_default=True,
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    # Paths
    input_path: Path = Field(description="Input video file path")
    output_path: Path = Field(description="Output video file path")
    work_dir: Path = Field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "drapto",
        description="Working directory for temporary files"
    )
    
    # Video settings
    target_vmaf: float = Field(
        default=defaults.TARGET_VMAF,
        description="Target VMAF score (0-100)"
    )
    preset: int = Field(
        default=defaults.PRESET,
        ge=0,
        le=13,
        description="SVT-AV1 preset (0-13, higher is faster)"
    )
    svt_params: str = Field(
        default=defaults.SVT_PARAMS,
        description="Additional SVT-AV1 parameters"
    )
    crop_filter: Optional[str] = Field(
        default=None,
        description="FFmpeg crop filter (e.g. 'crop=1920:800:0:140')"
    )
    
    # Hardware settings
    hw_device: Optional[str] = Field(
        default=None,
        description="Hardware device for acceleration"
    )
    hw_accel: Optional[str] = Field(
        default=None,
        description="Hardware acceleration method"
    )
    
    # Resource limits
    cpu_limit: Optional[int] = Field(
        default=None,
        description="CPU usage limit percentage (0-100)"
    )
    memory_limit: Optional[int] = Field(
        default=None,
        description="Memory usage limit in MB"
    )
    disk_limit: Optional[int] = Field(
        default=None,
        description="Disk space limit in MB"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    log_file: Optional[Path] = Field(
        default=None,
        description="Log file path"
    )
    
    def __init__(self, **data):
        """Initialize config with validation."""
        super().__init__(**data)
        self._validate_paths()
        self._validate_hardware()
        self._setup_logging()
    
    def _validate_paths(self) -> None:
        """Validate and create required paths."""
        # Ensure work directory exists
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # Check input file exists
        if not self.input_path.exists():
            raise ValueError(f"Input file not found: {self.input_path}")
            
        # Check input file is readable
        if not os.access(self.input_path, os.R_OK):
            raise ValueError(f"Input file not readable: {self.input_path}")
            
        # Check output directory exists or can be created
        if not self.output_path.parent.exists():
            self.output_path.parent.mkdir(parents=True)
            
        # Check output directory is writable
        if not os.access(self.output_path.parent, os.W_OK):
            raise ValueError(
                f"Output directory not writable: {self.output_path.parent}"
            )
            
        # Check work directory is writable
        if not os.access(self.work_dir, os.W_OK):
            raise ValueError(f"Work directory not writable: {self.work_dir}")
    
    def _validate_hardware(self) -> None:
        """Validate hardware acceleration settings."""
        if self.hw_accel and not self.hw_device:
            # Try to detect hardware device
            if platform.system() == "Linux":
                if shutil.which("nvidia-smi"):
                    self.hw_device = "/dev/dri/renderD128"
                elif os.path.exists("/dev/dri/renderD128"):
                    self.hw_device = "/dev/dri/renderD128"
            
            if not self.hw_device:
                raise ValueError(
                    "Hardware acceleration requested but no device specified "
                    "or detected"
                )
    
    def _setup_logging(self) -> None:
        """Configure logging based on settings."""
        logger.remove()  # Remove default handler
        
        # Add console handler
        logger.add(
            sink=lambda msg: print(msg),
            level=self.log_level,
            format="<level>{level}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:"
                   "<cyan>{line}</cyan> - <level>{message}</level>"
        )
        
        # Add file handler if specified
        if self.log_file:
            logger.add(
                sink=str(self.log_file),
                level=self.log_level,
                rotation="100 MB",
                retention="1 week"
            )
    
    def get_resource_limits(self) -> Dict[str, Optional[int]]:
        """Get resource limits as dictionary."""
        return {
            "cpu": self.cpu_limit,
            "memory": self.memory_limit,
            "disk": self.disk_limit
        }
