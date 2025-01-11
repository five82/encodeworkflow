"""HDR detection utilities."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Set, Any, List

from .types import VideoStreamInfo, HDRInfo
from .errors import HDRDetectionError

# Valid HDR format combinations
HDR_FORMATS = {
    'HDR10': {
        'color_transfer': {'smpte2084'},  # PQ
        'color_primaries': {'bt2020'},
        'color_space': {'bt2020nc', 'bt2020c'},
        'bit_depth': {10}
    },
    'Dolby Vision': {
        'color_transfer': {'smpte2084'},  # Must be PQ
        'color_primaries': {'bt2020'},
        'color_space': {'bt2020nc', 'bt2020c'},
        'bit_depth': {10}  # Always encode in 10-bit
    }
}

# Black level constants for DVD/Blu-ray sources
MIN_BLACK_LEVEL = 16
MAX_BLACK_LEVEL = 256
DEFAULT_SDR_BLACK_LEVEL = 16  # Standard for DVD/Blu-ray
DEFAULT_HDR_BLACK_LEVEL = 64  # Higher default for HDR content

def detect_hdr(stream_info: VideoStreamInfo) -> Optional[HDRInfo]:
    """Detect HDR format from stream info.

    Supports HDR10 and Dolby Vision from DVD, Blu-ray, and UHD Blu-ray sources.
    All content will be encoded in 10-bit with SVT-AV1.

    Args:
        stream_info: Video stream information

    Returns:
        HDRInfo if HDR format detected, None if SDR

    Raises:
        HDRDetectionError: If stream properties are invalid or inconsistent
    """
    if not stream_info:
        raise HDRDetectionError("No stream info provided")

    # Normalize color properties to lowercase
    color_transfer = stream_info.color_transfer.lower() if stream_info.color_transfer else ''
    color_primaries = stream_info.color_primaries.lower() if stream_info.color_primaries else ''
    color_space = stream_info.color_space.lower() if stream_info.color_space else ''
    bit_depth = stream_info.bit_depth

    # Check for Dolby Vision profile in side_data_list or is_dolby_vision flag
    side_data_list = getattr(stream_info, 'side_data_list', [])
    has_dv_profile = any('dv_profile' in data for data in side_data_list) if side_data_list else False
    
    # First check for Dolby Vision since it's most specific
    if has_dv_profile or stream_info.is_dolby_vision:
        # Validate Dolby Vision color properties
        if not _validate_color_properties('Dolby Vision', color_transfer, color_primaries, color_space, bit_depth):
            raise HDRDetectionError(
                "Invalid color properties for Dolby Vision content. "
                f"Expected: {HDR_FORMATS['Dolby Vision']}, "
                f"Got: transfer={color_transfer}, primaries={color_primaries}, "
                f"space={color_space}, bit_depth={bit_depth}")
        
        # Detect black level for HDR content
        black_level = detect_black_level(stream_info.input_path, True)
        
        return HDRInfo(
            format='dolby_vision',
            is_hdr=True,
            is_dolby_vision=True,
            black_level=black_level
        )

    # Check for HDR10
    if _validate_color_properties('HDR10', color_transfer, color_primaries, color_space, bit_depth):
        black_level = detect_black_level(stream_info.input_path, True)
        return HDRInfo(
            format='hdr10',
            is_hdr=True,
            is_dolby_vision=False,
            black_level=black_level
        )

    # Content is SDR if no HDR format detected
    return None

def _validate_color_properties(
    hdr_format: str,
    color_transfer: str,
    color_primaries: str,
    color_space: str,
    bit_depth: int
) -> bool:
    """Validate color properties match HDR format requirements.

    Args:
        hdr_format: HDR format to validate against
        color_transfer: Color transfer characteristic
        color_primaries: Color primaries
        color_space: Color space
        bit_depth: Bit depth

    Returns:
        True if properties are valid for format
    """
    format_reqs = HDR_FORMATS[hdr_format]

    # All properties must be present and match format requirements
    return (
        color_transfer in format_reqs['color_transfer'] and
        color_primaries in format_reqs['color_primaries'] and
        color_space in format_reqs['color_space'] and
        bit_depth in format_reqs['bit_depth']
    )

def detect_black_level(input_path: Path, is_hdr: bool) -> int:
    """Detect black level by sampling frames.

    For SDR content from DVD/Blu-ray, uses standard black level of 16.
    For HDR content from UHD Blu-ray:
    1. Samples frames to find typical black level
    2. Uses average of detected black levels
    3. Clamps to valid range [16, 256]

    Args:
        input_path: Path to input video file
        is_hdr: Whether the content is HDR

    Returns:
        Black level threshold for the content

    Raises:
        HDRDetectionError: If black level detection fails
        FileNotFoundError: If input file does not exist
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    # Use default values if not HDR (DVD/Blu-ray)
    if not is_hdr:
        return DEFAULT_SDR_BLACK_LEVEL

    try:
        # Sample frames to detect black level
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-vf', 'blackdetect=d=0:pix_th=0.00',
            '-f', 'null',
            '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse black frame detection output
        black_levels = []
        for line in result.stderr.split('\n'):
            if 'black_level' in line:
                try:
                    level = int(line.split('black_level:')[1].split()[0])
                    black_levels.append(level)
                except (IndexError, ValueError):
                    continue

        # Calculate average black level
        if black_levels:
            avg_level = sum(black_levels) / len(black_levels)
            # Clamp to valid range for UHD Blu-ray
            black_level = max(MIN_BLACK_LEVEL, min(int(avg_level), MAX_BLACK_LEVEL))
        else:
            # Use default HDR black level if detection fails
            black_level = DEFAULT_HDR_BLACK_LEVEL

        return black_level

    except subprocess.CalledProcessError as e:
        raise HDRDetectionError(f"Black level detection failed: {e.stderr}")
    except Exception as e:
        raise HDRDetectionError(f"Black level detection failed: {str(e)}")
