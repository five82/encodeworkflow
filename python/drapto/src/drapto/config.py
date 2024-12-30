"""Configuration module."""

import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict

from loguru import logger
from pydantic import BaseModel, Field

from . import default_config as defaults


class EncodingConfig(BaseModel):
    """Configuration for video encoding."""
    
    # Paths
    script_dir: Path = Field(
        default_factory=lambda: defaults.SCRIPT_DIR,
        description="Script directory"
    )
    ffmpeg: Path = Field(
        default_factory=lambda: defaults.FFMPEG,
        description="FFmpeg binary path"
    )
    ffprobe: Path = Field(
        default_factory=lambda: defaults.FFPROBE,
        description="FFprobe binary path"
    )
    
    # Encoding settings
    preset: int = Field(defaults.PRESET, description="SVT-AV1 preset (0-13)")
    crf_sd: int = Field(defaults.CRF_SD, description="CRF for SD videos (width <= 1280)")
    crf_hd: int = Field(defaults.CRF_HD, description="CRF for HD videos (width <= 1920)")
    crf_uhd: int = Field(defaults.CRF_UHD, description="CRF for UHD videos (width > 1920)")
    svt_params: str = Field(
        defaults.SVT_PARAMS,
        description="SVT-AV1 parameters"
    )
    pix_fmt: str = Field(defaults.PIX_FMT, description="Pixel format")
    
    # Hardware acceleration
    hw_accel_opts: Optional[str] = Field(defaults.HW_ACCEL_OPTS, description="Hardware acceleration options")
    
    # Feature flags
    is_dolby_vision: bool = Field(False, description="Whether content is Dolby Vision")
    disable_crop: bool = Field(defaults.DISABLE_CROP, description="Disable automatic crop detection")
    enable_chunked_encoding: bool = Field(defaults.ENABLE_CHUNKED_ENCODING, description="Enable chunked encoding")
    
    # Chunked encoding settings
    segment_length: int = Field(defaults.SEGMENT_LENGTH, description="Length of each segment in seconds")
    target_vmaf: float = Field(defaults.TARGET_VMAF, description="Target VMAF score")
    vmaf_sample_count: int = Field(defaults.VMAF_SAMPLE_COUNT, description="Number of VMAF samples")  # Renamed from vmaf_samples
    vmaf_sample_length: int = Field(defaults.VMAF_SAMPLE_LENGTH, description="Length of each VMAF sample in seconds")
    
    # Directory settings
    temp_dir: Optional[Path] = Field(
        default=None,
        description="Override default temporary directory location"
    )
    working_dir: Optional[Path] = Field(
        default=None,
        description="Override default working directory location"
    )
    segments_dir: Path = Field(
        default_factory=lambda: defaults.SEGMENTS_DIR,
        description="Directory for video segments"
    )
    encoded_segments_dir: Path = Field(
        default_factory=lambda: defaults.ENCODED_SEGMENTS_DIR,
        description="Directory for encoded segments"
    )
    
    # System info
    is_macos: bool = Field(
        default_factory=lambda: platform.system().lower() == "darwin",
        description="Whether running on macOS"
    )
    is_apple_silicon: bool = Field(
        default_factory=lambda: platform.machine().lower() in ["arm64", "aarch64"],
        description="Whether running on Apple Silicon"
    )
    jobs: int = Field(
        default_factory=lambda: os.cpu_count() or 1,
        description="Number of parallel jobs"
    )
    
    def __init__(
        self,
        target_vmaf: float = 95,
        preset: int = 8,
        vmaf_sample_count: int = 30,
        vmaf_sample_length: int = 2,
        svt_params: str = "tune=0:film-grain=8",
        hw_accel_opts: Optional[str] = None,
        working_dir: Optional[Path] = None,
        temp_dir: Optional[Path] = None,
        **data
    ):
        """Initialize encoding configuration.
        
        Args:
            target_vmaf: Target VMAF score
            preset: SVT-AV1 preset (0-13)
            vmaf_sample_count: Number of VMAF samples
            vmaf_sample_length: Length of each VMAF sample in seconds
            svt_params: SVT-AV1 parameters
            hw_accel_opts: Hardware acceleration options
            working_dir: Override default working directory location
            temp_dir: Override default temporary directory location
        """
        super().__init__(
            target_vmaf=target_vmaf,
            preset=preset,
            vmaf_sample_count=vmaf_sample_count,
            vmaf_sample_length=vmaf_sample_length,
            svt_params=svt_params,
            hw_accel_opts=hw_accel_opts,
            working_dir=working_dir,
            temp_dir=temp_dir,
            **data
        )
        
        # Initialize paths
        self._init_paths()
        
        # Ensure CRF values are set
        self.crf_sd = getattr(self, 'crf_sd', 25)
        self.crf_hd = getattr(self, 'crf_hd', 25)
        self.crf_uhd = getattr(self, 'crf_uhd', 29)
    
    def _init_paths(self) -> None:
        """Initialize and validate paths."""
        # Convert paths to absolute
        self.script_dir = self.script_dir.resolve()
        self.ffmpeg = self.ffmpeg.resolve()
        self.ffprobe = self.ffprobe.resolve()
        if self.working_dir:
            self.working_dir = self.working_dir.resolve()
        if self.temp_dir:
            self.temp_dir = self.temp_dir.resolve()
        if self.segments_dir:
            self.segments_dir = self.segments_dir.resolve()
        if self.encoded_segments_dir:
            self.encoded_segments_dir = self.encoded_segments_dir.resolve()
            
        # Validate required paths exist
        for name, path in [
            ("FFmpeg", self.ffmpeg),
            ("FFprobe", self.ffprobe)
        ]:
            if not path.exists():
                logger.warning(f"{name} not found at {path}")
                
        logger.debug(f"Using paths: ffmpeg={self.ffmpeg}, ffprobe={self.ffprobe}")
        logger.debug(f"Using working directory: {self.working_dir}")
        self._setup_directories()
        
    def _setup_directories(self) -> None:
        """Setup required directories."""
        for dir_path in [self.temp_dir, self.segments_dir, self.encoded_segments_dir, self.working_dir]:
            if dir_path:
                dir_path.mkdir(parents=True, exist_ok=True)
    
    def cleanup_temp_dirs(self) -> None:
        """Clean up temporary directories."""
        for dir_path in [self.segments_dir, self.encoded_segments_dir, self.working_dir]:
            if dir_path.exists():
                shutil.rmtree(dir_path)
    
    def get_crf(self, width: int) -> int:
        """Get CRF value based on video width.
        
        Args:
            width: Video width in pixels
            
        Returns:
            CRF value
        """
        if width <= 1280:
            return self.crf_sd
        elif width <= 1920:
            return self.crf_hd
        else:
            return self.crf_uhd
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True