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
        """Analyze video stream and return information.
        
        This performs a comprehensive analysis including:
        - Basic stream properties (dimensions, frame rate)
        - Color space and HDR information
        - Black bar detection
        - Quality settings selection
        
        Args:
            input_path: Path to input video file
            
        Returns:
            VideoStreamInfo if successful, None if analysis fails
        """
        try:
            # Get stream info using FFprobe
            cmd = [
                self.config.get('ffprobe', 'ffprobe'),
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 
                'stream=width,height,r_frame_rate,pix_fmt,'
                'color_transfer,color_primaries,color_space,bits_per_raw_sample',
                '-of', 'json',
                str(input_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            if not data.get('streams'):
                self._logger.error("No video streams found")
                return None
                
            stream = data['streams'][0]
            
            # Parse frame rate
            try:
                num, den = map(int, stream.get('r_frame_rate', '0/1').split('/'))
                frame_rate = num / den if den else 0.0
            except (ValueError, ZeroDivisionError):
                frame_rate = 0.0
                
            # Get bit depth from pixel format
            pixel_format = stream.get('pix_fmt', 'yuv420p')
            bit_depth = 8
            if 'p10' in pixel_format:
                bit_depth = 10
            elif 'p12' in pixel_format:
                bit_depth = 12
                
            # Create base stream info
            info = VideoStreamInfo(
                width=stream.get('width', 0),
                height=stream.get('height', 0),
                color_transfer=stream.get('color_transfer'),
                color_primaries=stream.get('color_primaries'),
                color_space=stream.get('color_space'),
                pixel_format=pixel_format,
                frame_rate=frame_rate,
                bit_depth=bit_depth
            )
            
            # Detect HDR and Dolby Vision
            hdr_info = detect_hdr(info, input_path)
            info.is_hdr = hdr_info.is_hdr
            info.is_dolby_vision = hdr_info.is_dolby_vision
            
            # Detect black bars (using HDR-aware threshold)
            crop_info = detect_black_bars(input_path, self.config, info)
            info.crop_info = crop_info
            
            # Get quality settings
            info.quality_settings = get_quality_settings(info)
            
            return info
            
        except Exception as e:
            self._logger.error("Stream analysis failed: %s", e)
            return None
