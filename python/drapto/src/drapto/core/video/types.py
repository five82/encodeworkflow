"""Common video analysis types."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

from .errors import CropValidationError


@dataclass
class CropInfo:
    """Crop detection results.
    
    Attributes:
        x: X offset for cropping
        y: Y offset for cropping
        width: Width after cropping
        height: Height after cropping
        enabled: Whether cropping should be applied
    """
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    enabled: bool = False

    def validate(self, original_width: int, original_height: int) -> None:
        """Validate crop values against original dimensions.
        
        Args:
            original_width: Original video width
            original_height: Original video height
            
        Raises:
            CropValidationError: If crop values are invalid
        """
        # Check if dimensions are smaller than original
        if self.width > original_width:
            raise CropValidationError(
                "Crop width cannot be larger than original width",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )
        if self.height > original_height:
            raise CropValidationError(
                "Crop height cannot be larger than original height",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )

        # Check if offsets are non-negative
        if self.x < 0:
            raise CropValidationError(
                "X offset must be non-negative",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )
        if self.y < 0:
            raise CropValidationError(
                "Y offset must be non-negative",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )

        # Check if dimensions are even numbers (required for video encoding)
        if self.width % 2 != 0:
            raise CropValidationError(
                "Crop width must be an even number",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )
        if self.height % 2 != 0:
            raise CropValidationError(
                "Crop height must be an even number",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )

        # Check if offsets are even numbers
        if self.x % 2 != 0:
            raise CropValidationError(
                "X offset must be an even number",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )
        if self.y % 2 != 0:
            raise CropValidationError(
                "Y offset must be an even number",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )

        # Check if resulting dimensions maintain aspect ratio within 1%
        original_ratio = original_width / original_height
        crop_ratio = self.width / self.height
        ratio_diff = abs(original_ratio - crop_ratio) / original_ratio
        if ratio_diff > 0.01:  # 1% tolerance
            raise CropValidationError(
                "Crop dimensions do not maintain original aspect ratio",
                original_width, original_height,
                self.width, self.height, self.x, self.y
            )

    def to_ffmpeg_filter(self) -> Optional[str]:
        """Convert crop info to FFmpeg filter string.
        
        Returns:
            FFmpeg crop filter string if enabled, None otherwise
        """
        if not self.enabled:
            return None
        return f"crop={self.width}:{self.height}:{self.x}:{self.y}"


@dataclass
class QualitySettings:
    """Encoding quality settings.
    
    Attributes:
        crf: Constant Rate Factor value
        preset: Encoding preset (e.g. medium, slow)
        max_bitrate: Maximum bitrate in bits per second
        bufsize: Buffer size in bits
    """
    crf: int
    preset: str = 'medium'
    max_bitrate: Optional[int] = None
    bufsize: Optional[int] = None


@dataclass
class HDRInfo:
    """HDR information for video."""
    format: str
    is_hdr: bool = False
    is_dolby_vision: bool = False
    black_level: Optional[int] = None


@dataclass
class VideoStreamInfo:
    """Information about a video stream.
    
    Attributes:
        width: Video width in pixels
        height: Video height in pixels
        color_transfer: Color transfer characteristics (e.g. bt709, smpte2084)
        color_primaries: Color primaries (e.g. bt709, bt2020)
        color_space: Color space (e.g. bt709, bt2020nc)
        pixel_format: Pixel format (e.g. yuv420p, yuv420p10le)
        frame_rate: Frame rate in frames per second
        bit_depth: Bits per color component
        is_hdr: Whether the stream is HDR
        is_dolby_vision: Whether the stream has Dolby Vision metadata
        crop_info: Optional black bar detection info
        quality_settings: Optional encoding quality settings
        hdr_info: Optional HDR detection info
        input_path: Optional input path
        side_data_list: Optional list of side data dictionaries from FFprobe
    """
    width: int
    height: int
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None
    color_space: Optional[str] = None
    pixel_format: str = 'yuv420p'
    frame_rate: float = 0.0
    bit_depth: int = 8
    is_hdr: bool = False
    is_dolby_vision: bool = False
    crop_info: Optional[CropInfo] = None
    quality_settings: Optional[QualitySettings] = None
    hdr_info: Optional[HDRInfo] = None
    input_path: Optional[Path] = None
    side_data_list: Optional[List[Dict[str, Any]]] = None
