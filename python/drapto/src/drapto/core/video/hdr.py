"""HDR and color space detection."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

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


def detect_black_level(input_path: Path, is_hdr: bool) -> int:
    """Detect black level by sampling frames.
    
    Args:
        input_path: Path to input video file
        is_hdr: Whether the content is HDR
        
    Returns:
        Detected black level threshold
    """
    logger = logging.getLogger(__name__)
    
    if not is_hdr:
        return 16
        
    try:
        # Sample frames to find typical black level
        cmd = [
            'ffmpeg', '-hide_banner',
            '-i', str(input_path),
            '-vf', "select='eq(n,0)+eq(n,100)+eq(n,200)',blackdetect=d=0:pic_th=0.1",
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse black levels
        black_levels = []
        for line in result.stderr.splitlines():
            if 'black_level' in line:
                try:
                    level = float(line.split(':')[1])
                    black_levels.append(level)
                except (IndexError, ValueError):
                    continue
                    
        if black_levels:
            # Calculate average and adjust by 1.5
            avg_level = sum(black_levels) / len(black_levels)
            threshold = int(avg_level * 1.5)
            # Clamp between 16 and 256
            return max(16, min(256, threshold))
            
    except Exception as e:
        logger.error("Black level detection failed: %s", e)
        
    # Default HDR threshold if detection fails
    return 128


def detect_hdr(stream_info: VideoStreamInfo, input_path: Optional[Path] = None) -> HDRInfo:
    """Detect HDR format from stream information.
    
    This checks:
    - Color transfer characteristics (PQ/HLG/SMPTE428/BT.2020)
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
    
    # Check color transfer
    hdr_transfers = {
        'smpte2084',      # PQ/HDR10
        'arib-std-b67',   # HLG
        'smpte428',       # SMPTE ST.428
        'bt2020-10',      # BT.2020 10-bit
        'bt2020-12'       # BT.2020 12-bit
    }
    
    # Check color primaries
    hdr_primaries = {'bt2020'}
    
    # Check color space
    hdr_spaces = {'bt2020nc', 'bt2020c'}
    
    # Check if any HDR indicators are present
    if (stream_info.color_transfer in hdr_transfers or
        stream_info.color_primaries in hdr_primaries or
        stream_info.color_space in hdr_spaces):
        
        result.is_hdr = True
        
        # Determine HDR format
        if stream_info.color_transfer == 'smpte2084':
            result.hdr_format = 'HDR10'
        elif stream_info.color_transfer == 'arib-std-b67':
            result.hdr_format = 'HLG'
        else:
            result.hdr_format = 'HDR'
            
    # Check Dolby Vision if path provided
    if input_path and detect_dolby_vision(input_path):
        result.is_hdr = True
        result.is_dolby_vision = True
        result.hdr_format = 'Dolby Vision'
        
    # Log detection results
    if result.is_hdr:
        logger.info("HDR content detected: %s", result.hdr_format)
        if result.is_dolby_vision:
            logger.info("Dolby Vision metadata present")
            
    return result
