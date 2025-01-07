"""HDR and color space detection."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from .types import VideoStreamInfo, HDRInfo


def detect_dolby_vision(input_path: Path) -> bool:
    """Detect Dolby Vision using mediainfo.
    
    For UHD Blu-ray rips from MakeMKV, Dolby Vision will be consistently marked
    in the mediainfo output.
    
    Args:
        input_path: Path to input video file
        
    Returns:
        True if Dolby Vision metadata detected, False otherwise
    """
    logger = logging.getLogger(__name__)
    try:
        cmd = ['mediainfo', str(input_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        is_dv = 'Dolby Vision' in result.stdout
        if is_dv:
            logger.info("Dolby Vision detected")
        return is_dv
        
    except Exception as e:
        logger.error("Dolby Vision detection failed: %s", e)
        return False


def detect_black_level(input_path: Path, is_hdr: bool) -> int:
    """Detect black level by sampling frames.
    
    For SDR content, uses standard black level of 16.
    For HDR content:
    1. Samples frames to find typical black level
    2. Adjusts threshold based on measured black level
    3. Clamps to valid range [16, 256]
    
    Args:
        input_path: Path to input video file
        is_hdr: Whether the content is HDR
        
    Returns:
        Black level threshold for the content
    """
    logger = logging.getLogger(__name__)
    
    # Use standard black level for SDR
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
        
        # Default to SDR black level on error
        if result.returncode != 0:
            logger.error("Black level detection failed")
            return 16
            
        # Parse black levels from output
        black_levels = []
        for line in result.stderr.splitlines():
            if 'black_level' in line:
                try:
                    level = float(line.split(':')[1].strip())
                    black_levels.append(level)
                except (IndexError, ValueError):
                    continue
                    
        if not black_levels:
            logger.warning("No black levels found, using default")
            return 16
            
        # Calculate average and adjust
        avg_level = sum(black_levels) / len(black_levels)
        threshold = int(avg_level * 1.5)  # Multiply by 1.5 like bash script
        
        # Clamp to valid range
        return max(16, min(256, threshold))
        
    except Exception as e:
        logger.error("Black level detection failed: %s", e)
        return 16


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
    if input_path:
        is_dv = detect_dolby_vision(input_path)
        if is_dv:
            result.is_hdr = True
            result.is_dolby_vision = True
            result.hdr_format = 'Dolby Vision'
            
    # Log detection results
    if result.is_hdr:
        logger.info("HDR content detected: %s", result.hdr_format)
        if result.is_dolby_vision:
            logger.info("Dolby Vision metadata present")
            
    return result
