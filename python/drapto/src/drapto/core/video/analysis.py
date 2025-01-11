"""Video stream analysis and metadata."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Any, List, Union

from .types import VideoStreamInfo, HDRInfo, CropInfo, QualitySettings
from .hdr import detect_hdr
from .cropping import detect_black_bars
from .quality import get_quality_settings
from .errors import StreamAnalysisError

# Validation constants
MIN_DIMENSION = 16  # Minimum video dimension
MAX_DIMENSION = 8192  # Maximum video dimension (8K)
MIN_FRAME_RATE = 1  # Minimum frame rate
MAX_FRAME_RATE = 300  # Maximum frame rate
VALID_BIT_DEPTHS = {8, 10, 12}  # Valid bit depths
VALID_COLOR_SPACES = {'bt709', 'bt2020nc', 'bt2020c', 'smpte170m'}  # Common color spaces
VALID_COLOR_TRANSFERS = {'bt709', 'smpte2084', 'arib-std-b67', 'smpte428'}  # Common transfer functions
VALID_COLOR_PRIMARIES = {'bt709', 'bt2020', 'bt470bg', 'smpte432'}  # Common color primaries

class VideoAnalyzer:
    """Video stream analysis utilities."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize analyzer with config.
        
        Args:
            config: Configuration dictionary with FFmpeg paths and options
        """
        self.config = config
        self._logger = logging.getLogger(__name__)
        
    def detect_black_bars(self, input_path: Path, stream_info: Optional[VideoStreamInfo] = None) -> Optional[str]:
        """Detect black bars in video.
        
        Args:
            input_path: Path to input video file
            stream_info: Optional video stream info for HDR-aware threshold
            
        Returns:
            FFmpeg crop filter string if black bars detected, None otherwise
        """
        crop_info = detect_black_bars(input_path, self.config, stream_info)
        if crop_info and crop_info.enabled:
            return f"crop={crop_info.width}:{crop_info.height}:{crop_info.x}:{crop_info.y}"
        return None
        
    def get_quality_settings(self, stream_info: VideoStreamInfo) -> QualitySettings:
        """Get quality settings for stream.
        
        Args:
            stream_info: Video stream information
            
        Returns:
            Quality settings for encoding
        """
        return get_quality_settings(stream_info)
        
    def analyze_stream(self, input_path: Path) -> Optional[VideoStreamInfo]:
        """Analyze video stream and gather information.

        Args:
            input_path: Path to input video file

        Returns:
            VideoStreamInfo if successful

        Raises:
            StreamAnalysisError: If stream properties are invalid
            FileNotFoundError: If input file does not exist
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input file does not exist: {input_path}")

        try:
            # Get stream info from FFprobe
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-select_streams', 'v:0',
                str(input_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise StreamAnalysisError(f"FFprobe analysis failed: {result.stderr}")

            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                raise StreamAnalysisError(f"Failed to parse FFprobe output: {str(e)}")

            if not data.get('streams'):
                raise StreamAnalysisError("No video streams found in input file")

            stream = data['streams'][0]
            
            # Validate dimensions
            width = stream.get('width', 0)
            height = stream.get('height', 0)
            if not (MIN_DIMENSION <= width <= MAX_DIMENSION):
                raise StreamAnalysisError(
                    f"Invalid video width: {width}. Must be between {MIN_DIMENSION} and {MAX_DIMENSION}")
            if not (MIN_DIMENSION <= height <= MAX_DIMENSION):
                raise StreamAnalysisError(
                    f"Invalid video height: {height}. Must be between {MIN_DIMENSION} and {MAX_DIMENSION}")

            # Parse and validate frame rate
            frame_rate = self._parse_frame_rate(stream.get('r_frame_rate', ''))
            if not (MIN_FRAME_RATE <= frame_rate <= MAX_FRAME_RATE):
                raise StreamAnalysisError(
                    f"Invalid frame rate: {frame_rate}. Must be between {MIN_FRAME_RATE} and {MAX_FRAME_RATE}")

            # Parse and validate bit depth
            pixel_format = stream.get('pix_fmt', '')
            try:
                bit_depth = self._get_bit_depth(pixel_format)
                if bit_depth not in VALID_BIT_DEPTHS:
                    raise StreamAnalysisError(
                        f"Invalid bit depth {bit_depth} from pixel format '{pixel_format}'. Must be one of {VALID_BIT_DEPTHS}")
            except ValueError as e:
                raise StreamAnalysisError(str(e))

            # Create stream info with validated values
            info = VideoStreamInfo(
                width=width,
                height=height,
                color_transfer=stream.get('color_transfer', ''),
                color_primaries=stream.get('color_primaries', ''),
                color_space=stream.get('color_space', ''),
                pixel_format=pixel_format,
                frame_rate=frame_rate,
                bit_depth=bit_depth,
                input_path=input_path
            )

            # Optional validation for color properties if present
            if info.color_space and info.color_space not in VALID_COLOR_SPACES:
                self._logger.warning(f"Unexpected color space: {info.color_space}")
            if info.color_transfer and info.color_transfer not in VALID_COLOR_TRANSFERS:
                self._logger.warning(f"Unexpected color transfer: {info.color_transfer}")
            if info.color_primaries and info.color_primaries not in VALID_COLOR_PRIMARIES:
                self._logger.warning(f"Unexpected color primaries: {info.color_primaries}")

            # Detect HDR format
            info.hdr_info = detect_hdr(info)
            info.is_hdr = info.hdr_info is not None
            info.is_dolby_vision = info.hdr_info and info.hdr_info.format == 'dolby_vision'

            # Detect crop info
            crop_filter = self.detect_black_bars(input_path, info)
            if crop_filter:
                # Parse crop filter string to get dimensions
                # Format: crop=width:height:x:y
                parts = crop_filter.split('=')[1].split(':')
                info.crop_info = CropInfo(
                    enabled=True,
                    width=int(parts[0]),
                    height=int(parts[1]),
                    x=int(parts[2]),
                    y=int(parts[3])
                )

            return info

        except subprocess.CalledProcessError as e:
            raise StreamAnalysisError(f"FFprobe command failed: {e.stderr}")
        except Exception as e:
            if isinstance(e, StreamAnalysisError):
                raise
            if "ffprobe" in str(e).lower():
                raise StreamAnalysisError(f"FFprobe command failed: {str(e)}")
            raise StreamAnalysisError(str(e))

    def _parse_frame_rate(self, rate_str: str) -> float:
        """Parse frame rate string into float.

        Args:
            rate_str: Frame rate string in format 'num/den'

        Returns:
            Frame rate as float
        """
        try:
            if not rate_str:
                return 0.0
            num, den = map(int, rate_str.split('/'))
            return num / den if den else 0.0
        except (ValueError, ZeroDivisionError):
            return 0.0

    def _get_bit_depth(self, pixel_format: str) -> int:
        """Get bit depth from pixel format.

        Args:
            pixel_format: FFmpeg pixel format string

        Returns:
            Bit depth (8, 10, or 12)
            
        Raises:
            ValueError: If pixel format indicates unsupported bit depth
        """
        if 'p16' in pixel_format:
            raise ValueError(f"Invalid bit depth: 16-bit pixel format '{pixel_format}' not supported")
        elif 'p10' in pixel_format:
            return 10
        elif 'p12' in pixel_format:
            return 12
        return 8
