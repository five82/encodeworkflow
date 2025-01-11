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
            VideoStreamInfo if successful, None if analysis fails
        """
        if not input_path.exists():
            self._logger.error(f"Input file does not exist: {input_path}")
            return None

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
            data = json.loads(result.stdout)

            if not data.get('streams'):
                self._logger.error("No video streams found")
                return None

            stream = data['streams'][0]
            info = VideoStreamInfo(
                width=stream.get('width', 0),
                height=stream.get('height', 0),
                color_transfer=stream.get('color_transfer', ''),
                color_primaries=stream.get('color_primaries', ''),
                color_space=stream.get('color_space', ''),
                pixel_format=stream.get('pix_fmt', 'yuv420p'),
                frame_rate=self._parse_frame_rate(stream.get('r_frame_rate', '')),
                bit_depth=self._get_bit_depth(stream.get('pix_fmt', '')),
                input_path=input_path
            )

            # Detect HDR format
            info.hdr_info = detect_hdr(info)
            info.is_hdr = info.hdr_info is not None
            info.is_dolby_vision = info.hdr_info and info.hdr_info.format == 'dolby_vision'

            # Detect black bars
            info.crop_info = detect_black_bars(input_path, self.config)

            return info

        except Exception as e:
            self._logger.error(f"Stream analysis failed: {e}")
            return None

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
        """
        if 'p10' in pixel_format:
            return 10
        elif 'p12' in pixel_format:
            return 12
        return 8
