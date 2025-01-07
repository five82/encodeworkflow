"""Quality settings selection."""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .types import VideoStreamInfo, QualitySettings


@dataclass
class QualitySettings:
    """Encoding quality settings.
    
    Attributes:
        crf: Constant Rate Factor value
        preset: Encoding preset (e.g. medium, slow)
        max_bitrate: Maximum bitrate in bits per second
        bufsize: Buffer size in bits
        svt_params: SVT-AV1 parameters
    """
    crf: int
    preset: int = 6
    max_bitrate: Optional[int] = None
    bufsize: Optional[int] = None
    svt_params: Optional[str] = None


def validate_preset(preset: int) -> int:
    """Validate and clamp SVT-AV1 preset value.
    
    Args:
        preset: Preset value to validate
        
    Returns:
        Validated preset value between 0-13
    """
    if not isinstance(preset, int):
        return 6  # Default preset
    return max(0, min(13, preset))  # Clamp between 0-13


def get_quality_settings(stream_info: VideoStreamInfo) -> QualitySettings:
    """Get quality settings for video stream.
    
    Args:
        stream_info: Video stream information
        
    Returns:
        Quality settings for encoding
    """
    try:
        # Default SVT-AV1 preset (6 is default from bash script)
        preset = validate_preset(6)
        
        # Set CRF based on resolution
        if stream_info.width > 1920 or stream_info.height > 1080:
            crf = 29  # UHD (4K and above)
        else:
            crf = 25  # SD/HD (720p/1080p)
            
        # Default SVT-AV1 parameters
        svt_params = "tune=0:film-grain=0:film-grain-denoise=0"
        
        # Bitrate settings based on resolution
        if stream_info.width >= 3840 or stream_info.height >= 2160:
            max_bitrate = 16_000_000  # 16 Mbps for UHD
            bufsize = 32_000_000      # 32 Mbps buffer
        elif stream_info.width >= 1920 or stream_info.height >= 1080:
            max_bitrate = 8_000_000   # 8 Mbps for HD
            bufsize = 16_000_000      # 16 Mbps buffer
        else:
            max_bitrate = 4_000_000   # 4 Mbps for SD
            bufsize = 8_000_000       # 8 Mbps buffer
            
        # Increase bitrate for high frame rate content
        if stream_info.frame_rate > 30:
            max_bitrate = int(max_bitrate * 1.5)  # 50% more for high fps
            bufsize = int(bufsize * 1.5)          # 50% more buffer for high fps
            
        return QualitySettings(
            crf=crf,
            preset=preset,
            max_bitrate=max_bitrate,
            bufsize=bufsize,
            svt_params=svt_params
        )
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get quality settings: {e}")
        # Return default settings
        return QualitySettings(
            crf=25,  # Default to SD/HD CRF
            preset=validate_preset(6)  # Default SVT-AV1 preset
        )
