"""Video analysis utilities.

This module provides functionality for analyzing video streams, including:
- HDR format detection
- Black bar detection
- Quality settings selection
"""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from ...utils.validation import validate_input_file
from ...utils.logging import get_logger
from ..types import VideoStreamInfo, HDRInfo, CropInfo


class VideoAnalysisError(Exception):
    """Base class for video analysis errors."""
    
    def __init__(self, message: str, details: Optional[str] = None):
        """Initialize error.
        
        Args:
            message: Error message
            details: Optional technical details
        """
        self.message = message
        self.details = details
        super().__init__(message)


class HDRDetectionError(VideoAnalysisError):
    """Error detecting HDR format."""
    pass


class BlackBarDetectionError(VideoAnalysisError):
    """Error detecting black bars."""
    pass


class FFmpegError(VideoAnalysisError):
    """Error running FFmpeg command."""
    
    def __init__(self, message: str, cmd: Optional[str] = None, 
                 stderr: Optional[str] = None):
        """Initialize error.
        
        Args:
            message: Error message
            cmd: FFmpeg command that failed
            stderr: FFmpeg error output
        """
        details = f"Command: {cmd}\nError: {stderr}" if cmd else stderr
        super().__init__(message, details)
        self.cmd = cmd
        self.stderr = stderr


class MediaInfoError(VideoAnalysisError):
    """Error running mediainfo command."""
    
    def __init__(self, message: str, cmd: Optional[str] = None, 
                 stderr: Optional[str] = None):
        """Initialize error.
        
        Args:
            message: Error message
            cmd: MediaInfo command that failed
            stderr: MediaInfo error output
        """
        details = f"Command: {cmd}\nError: {stderr}" if cmd else stderr
        super().__init__(message, details)
        self.cmd = cmd
        self.stderr = stderr


def detect_dolby_vision(input_path: Path) -> bool:
    """Detect Dolby Vision using mediainfo.
    
    For UHD Blu-ray rips from MakeMKV, Dolby Vision will be consistently marked
    in the mediainfo output.
    
    Args:
        input_path: Path to input video file
        
    Returns:
        True if Dolby Vision metadata detected, False otherwise
        
    Raises:
        MediaInfoError: If mediainfo command fails
        FileNotFoundError: If input file does not exist
    """
    validate_input_file(input_path)
    logger = get_logger(__name__)
    
    try:
        cmd = ['mediainfo', str(input_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        is_dv = 'Dolby Vision' in result.stdout
        if is_dv:
            logger.info("Dolby Vision detected")
        return is_dv
        
    except subprocess.CalledProcessError as e:
        raise MediaInfoError(
            "MediaInfo command failed",
            cmd=' '.join(cmd),
            stderr=e.stderr
        ) from e
    except FileNotFoundError as e:
        raise MediaInfoError(
            "MediaInfo not found. Please install mediainfo."
        ) from e
    except Exception as e:
        raise MediaInfoError(f"Unexpected error: {e}") from e


def _get_video_duration(input_path: Path) -> float:
    """Get video duration in seconds.
    
    Args:
        input_path: Path to input video file
        
    Returns:
        Duration in seconds
        
    Raises:
        FFmpegError: If duration detection fails
    """
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(input_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
        
    except subprocess.CalledProcessError as e:
        raise FFmpegError(
            "Failed to get video duration",
            cmd=' '.join(cmd),
            stderr=e.stderr
        ) from e
    except ValueError as e:
        raise FFmpegError(
            "Invalid duration value from FFprobe",
            cmd=' '.join(cmd)
        ) from e


def _get_crop_samples(input_path: Path, duration: float, 
                     black_threshold: int) -> List[Tuple[int, int, int, int]]:
    """Get crop values from sample frames.
    
    Args:
        input_path: Path to input video file
        duration: Video duration in seconds
        black_threshold: Black level threshold
        
    Returns:
        List of (x, y, width, height) crop values
        
    Raises:
        FFmpegError: If crop detection fails
    """
    try:
        # Skip credits based on content length
        credits_skip = 0
        if duration > 3600:  # > 1 hour
            credits_skip = 180  # Skip 3 minutes
        elif duration > 1200:  # > 20 minutes
            credits_skip = 60   # Skip 1 minute
        elif duration > 300:    # > 5 minutes
            credits_skip = 30   # Skip 30 seconds
            
        # Adjust duration for credits
        if credits_skip > 0 and duration > credits_skip:
            duration -= credits_skip
            
        # Sample every 5 seconds
        interval = 5
        sample_count = int(duration / interval)
        if sample_count < 1:
            sample_count = 1
            
        # Build frame selection filter
        select_frames = '+'.join(
            f'eq(t,{i*interval})'
            for i in range(sample_count)
        )
        
        cmd = [
            'ffmpeg', '-hide_banner',
            '-i', str(input_path),
            '-vf', f"select='{select_frames}',cropdetect=limit={black_threshold}:round=2",
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse crop values
        crop_values = []
        for line in result.stderr.split('\n'):
            if 'crop=' in line:
                try:
                    crop_str = line.split('crop=')[1].split(' ')[0]
                    w, h, x, y = map(int, crop_str.split(':'))
                    crop_values.append((x, y, w, h))
                except (IndexError, ValueError):
                    continue
                    
        return crop_values
        
    except subprocess.CalledProcessError as e:
        raise FFmpegError(
            "Crop detection failed",
            cmd=' '.join(cmd),
            stderr=e.stderr
        ) from e


def detect_black_bars(input_path: Path, config: Dict[str, Any],
                     stream_info: Optional[VideoStreamInfo] = None) -> Optional[CropInfo]:
    """Detect black bars in video.
    
    Uses FFmpeg's cropdetect filter to analyze black bars.
    Samples multiple frames for accuracy, adjusting threshold based on HDR status
    and skipping opening/closing credits based on content length.
    
    Args:
        input_path: Path to input video file
        config: Configuration with FFmpeg paths
        stream_info: Optional video stream info for HDR-aware threshold
        
    Returns:
        Crop information if detection successful, None otherwise
        
    Raises:
        BlackBarDetectionError: If crop detection fails
        FileNotFoundError: If input file does not exist
        ValueError: If config is invalid
    """
    validate_input_file(input_path)
    
    if not config:
        raise ValueError("config cannot be None")
        
    logger = get_logger(__name__)
    
    try:
        # Get video duration
        duration = _get_video_duration(input_path)
        
        # Set initial crop threshold
        crop_threshold = 16  # Default SDR black level
        
        # Adjust threshold for HDR content
        if stream_info and stream_info.is_hdr:
            if stream_info.hdr_info and stream_info.hdr_info.black_level:
                crop_threshold = stream_info.hdr_info.black_level
            else:
                crop_threshold = 128  # Default HDR black level
                
        logger.info("Using black level threshold: %d", crop_threshold)
        
        # Get crop samples
        crop_values = _get_crop_samples(input_path, duration, crop_threshold)
        
        if not crop_values:
            logger.info("No crop values detected")
            return None
            
        # Find most common crop values
        crop_counts = {}
        for crop in crop_values:
            crop_counts[crop] = crop_counts.get(crop, 0) + 1
            
        most_common = max(crop_counts.items(), key=lambda x: x[1])[0]
        x, y, w, h = most_common
        
        # Create crop info
        crop_info = CropInfo(
            x=x,
            y=y,
            width=w,
            height=h,
            enabled=True
        )
        
        # Validate crop values
        if (crop_info.width % 2 != 0 or crop_info.height % 2 != 0 or
            crop_info.x < 0 or crop_info.y < 0):
            logger.warning("Invalid crop values detected: %s", crop_info)
            return None
            
        # Only crop if significant black bars found
        min_pixels = 10  # Minimum pixels to consider cropping
        if crop_info.x < min_pixels and crop_info.y < min_pixels:
            logger.info("Black bars too small to crop")
            return None
            
        logger.info("Detected crop values: %s", crop_info)
        return crop_info
        
    except FFmpegError as e:
        raise BlackBarDetectionError(
            "FFmpeg crop detection failed",
            details=str(e)
        ) from e
    except Exception as e:
        raise BlackBarDetectionError(f"Crop detection failed: {e}") from e


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
        
    Raises:
        HDRDetectionError: If black level detection fails
        FileNotFoundError: If input file does not exist
    """
    validate_input_file(input_path)
    
    if not is_hdr:
        return 16  # Standard black level for SDR
        
    logger = get_logger(__name__)
    try:
        # Sample a few frames to find the typical black level
        cmd = [
            'ffmpeg', '-hide_banner',
            '-i', str(input_path),
            '-vf', "select='eq(n,0)+eq(n,100)+eq(n,200)',blackdetect=d=0:pic_th=0.1",
            '-f', 'null', '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse black level from output
        black_levels = []
        for line in result.stderr.split('\n'):
            if 'black_level' in line:
                try:
                    level = float(line.split(':')[1])
                    black_levels.append(level)
                except (IndexError, ValueError):
                    continue
                    
        if not black_levels:
            logger.warning("No black levels detected, using default HDR black level")
            return 128
            
        # Calculate average black level
        avg_level = int(sum(black_levels) / len(black_levels))
        
        # Adjust threshold (multiply by 1.5 for safety margin)
        threshold = int(avg_level * 1.5)
        
        # Clamp to valid range
        threshold = max(16, min(256, threshold))
        logger.info("Detected HDR black level threshold: %d", threshold)
        return threshold
        
    except subprocess.CalledProcessError as e:
        raise HDRDetectionError(
            "FFmpeg black level detection failed",
            details=e.stderr
        ) from e
    except Exception as e:
        raise HDRDetectionError(f"Black level detection failed: {e}") from e


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
        
    Raises:
        HDRDetectionError: If HDR detection fails
        ValueError: If stream_info is invalid
    """
    if not stream_info:
        raise ValueError("stream_info cannot be None")
        
    logger = get_logger(__name__)
    
    try:
        # Initialize result
        hdr_info = HDRInfo()
        
        # Check Dolby Vision first if path provided
        if input_path:
            try:
                hdr_info.is_dolby_vision = detect_dolby_vision(input_path)
                if hdr_info.is_dolby_vision:
                    hdr_info.is_hdr = True
                    hdr_info.hdr_format = "Dolby Vision"
                    return hdr_info
            except MediaInfoError as e:
                logger.warning("Dolby Vision detection failed: %s", e)
                # Continue with other HDR checks
        
        # Check transfer characteristics
        if stream_info.color_transfer:
            transfer = stream_info.color_transfer.lower()
            if transfer in {'smpte2084', 'arib-std-b67'}:
                hdr_info.is_hdr = True
                hdr_info.hdr_format = "HDR10" if transfer == 'smpte2084' else "HLG"
            elif transfer in {'smpte428', 'bt2020-10', 'bt2020-12'}:
                hdr_info.is_hdr = True
                hdr_info.hdr_format = "BT.2020"
                
        # Check color primaries and space
        if (stream_info.color_primaries and 
            'bt2020' in stream_info.color_primaries.lower()):
            hdr_info.is_hdr = True
            if not hdr_info.hdr_format:
                hdr_info.hdr_format = "BT.2020"
                
        if (stream_info.color_space and 
            stream_info.color_space.lower() in {'bt2020nc', 'bt2020c'}):
            hdr_info.is_hdr = True
            if not hdr_info.hdr_format:
                hdr_info.hdr_format = "BT.2020"
                
        # Get black level if HDR
        if hdr_info.is_hdr and input_path:
            try:
                hdr_info.black_level = detect_black_level(input_path, True)
            except HDRDetectionError as e:
                logger.warning("Black level detection failed: %s", e)
                hdr_info.black_level = 128  # Default HDR black level
                
        logger.info("HDR detection results: %s", hdr_info)
        return hdr_info
        
    except Exception as e:
        raise HDRDetectionError(f"HDR format detection failed: {e}") from e
