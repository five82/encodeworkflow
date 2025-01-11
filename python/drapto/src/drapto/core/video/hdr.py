"""HDR detection utilities."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

from .types import VideoStreamInfo, HDRInfo
from .errors import HDRDetectionError, MediaInfoError, FFmpegError


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

    if not input_path.exists():
        logger.warning("Input file does not exist: %s", input_path)
        return False

    try:
        cmd = ['mediainfo', str(input_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        is_dv = 'Dolby Vision' in result.stdout
        if is_dv:
            logger.info("Dolby Vision detected")
        return is_dv

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning("MediaInfo command failed: %s", e)
        return False
    except Exception as e:
        logger.warning("Unexpected error in Dolby Vision detection: %s", e)
        return False


def detect_black_level(input_path: Path, is_hdr: bool) -> int:
    """Detect black level by sampling frames.

    For SDR content, uses standard black level of 16.
    For HDR content:
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

    if not is_hdr:
        return 16

    cmd = [
        'ffmpeg', '-i', str(input_path),
        '-vf', 'blackdetect',
        '-f', 'null', '-'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Extract black levels from output
        black_levels = []
        for line in result.stderr.splitlines():
            if 'black_level' in line:
                try:
                    level = int(line.split(':')[1])
                    black_levels.append(level)
                except (ValueError, IndexError):
                    continue

        if not black_levels:
            return 16  # Default to SDR black level if no levels detected

        # Use average of detected levels
        avg_level = sum(black_levels) // len(black_levels)
        
        # Clamp to valid range
        return max(16, min(avg_level, 256))

    except subprocess.CalledProcessError as e:
        raise FFmpegError(
            "FFmpeg black level detection failed",
            cmd=' '.join(cmd),
            stderr=e.stderr
        ) from e
    except Exception as e:
        raise HDRDetectionError(f"Black level detection failed: {e}") from e


def detect_hdr(stream_info: VideoStreamInfo) -> Optional[HDRInfo]:
    """Detect HDR format from stream info.

    Args:
        stream_info: Video stream information

    Returns:
        HDRInfo if HDR format detected, None if SDR
    """
    if not stream_info:
        return None

    # Check for Dolby Vision first if input path is available
    if stream_info.input_path and detect_dolby_vision(stream_info.input_path):
        return HDRInfo(format='dolby_vision')

    # Check color space attributes
    transfer = stream_info.color_transfer.lower()
    primaries = stream_info.color_primaries.lower()
    space = stream_info.color_space.lower()

    # HDR10
    if transfer == 'smpte2084' and primaries == 'bt2020':
        return HDRInfo(format='hdr10')

    # HLG
    if transfer == 'arib-std-b67' or transfer == 'hlg':
        return HDRInfo(format='hlg')

    # SMPTE ST 428
    if transfer == 'smpte428_1' or transfer == 'smpte428':
        return HDRInfo(format='smpte428')

    return None
