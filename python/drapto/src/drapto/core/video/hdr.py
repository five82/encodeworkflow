"""HDR and color space detection."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

from .types import VideoStreamInfo, HDRInfo


def detect_dolby_vision(input_path: Path) -> bool:
    """Detect Dolby Vision using mediainfo.
    
    Args:
        input_path: Path to input video file
        
    Returns:
        True if Dolby Vision metadata detected, False otherwise
    """
    logger = logging.getLogger(__name__)
    try:
        cmd = ['mediainfo', str(input_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return 'Dolby Vision' in result.stdout
    except Exception as e:
        logger.error("Dolby Vision detection failed: %s", e)
        return False


def detect_hdr(stream_info: VideoStreamInfo, input_path: Optional[Path] = None) -> HDRInfo:
    """Detect HDR format from stream information.
    
    This checks:
    - Color transfer characteristics (PQ/HLG)
    - Color primaries (BT.2020)
    - Color space (BT.2020)
    - Bit depth (10-bit)
    - Dolby Vision metadata
    
    Args:
        stream_info: Video stream information
        input_path: Optional path to input file for Dolby Vision detection
        
    Returns:
        HDR detection results
    """
    logger = logging.getLogger(__name__)
    
    # Initialize result
    result = HDRInfo()
    
    try:
        # Check for HDR transfer functions
        if stream_info.color_transfer:
            transfer = stream_info.color_transfer.lower()
            if transfer in ['smpte2084', 'arib-std-b67', 'smpte428', 'bt2020-10', 'bt2020-12']:
                result.is_hdr = True
                if transfer == 'smpte2084':
                    result.hdr_format = 'HDR10'
                elif transfer == 'arib-std-b67':
                    result.hdr_format = 'HLG'
                
        # Check color primaries
        if stream_info.color_primaries:
            primaries = stream_info.color_primaries.lower()
            if primaries == 'bt2020':
                result.is_hdr = True
                
        # Check color space
        if stream_info.color_space:
            color_space = stream_info.color_space.lower()
            if color_space in ['bt2020nc', 'bt2020c']:
                result.is_hdr = True
                
        # Check bit depth
        if stream_info.bit_depth >= 10:
            result.is_hdr = True
            
        # Check for Dolby Vision if path provided
        if input_path:
            result.is_dolby_vision = detect_dolby_vision(input_path)
            if result.is_dolby_vision:
                result.is_hdr = True
                result.hdr_format = 'Dolby Vision'
        
    except Exception as e:
        logger.error("HDR detection failed: %s", e)
        
    return result
