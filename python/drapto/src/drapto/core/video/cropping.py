"""Black bar detection utilities."""

import logging
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from .types import VideoStreamInfo, CropInfo
from .errors import BlackBarDetectionError, FFmpegError


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
            '-of', 'json',
            str(input_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
        
    except subprocess.CalledProcessError as e:
        raise FFmpegError(
            "Failed to get video duration",
            cmd=' '.join(cmd),
            stderr=e.stderr
        ) from e
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise FFmpegError(
            "Invalid duration value from FFprobe",
            cmd=' '.join(cmd)
        ) from e


def get_crop_threshold(stream_info: Optional[VideoStreamInfo] = None) -> int:
    """Get black level threshold for crop detection.
    
    Args:
        stream_info: Optional video stream info for HDR-aware threshold
        
    Returns:
        Black level threshold value
    """
    # Default threshold for SDR content
    threshold = 24
    
    if stream_info and stream_info.is_hdr:
        # Higher threshold for HDR content
        threshold = 48
        
        # Adjust based on transfer function
        if stream_info.color_transfer == 'smpte2084':  # PQ/HDR10
            threshold = 64
        elif stream_info.color_transfer == 'arib-std-b67':  # HLG
            threshold = 56
            
    return threshold


def get_credits_skip(duration: float) -> Tuple[float, float]:
    """Get time ranges to skip for credits.
    
    Args:
        duration: Video duration in seconds
        
    Returns:
        Tuple of (start_skip, end_skip) in seconds
    """
    # Skip first 2 minutes and last 3 minutes for longer content
    if duration > 3600:  # > 1 hour
        return (120.0, 180.0)
    # Skip first 1 minute and last 2 minutes for medium content    
    elif duration > 1800:  # > 30 minutes
        return (60.0, 120.0)
    # Skip first 30 seconds and last 1 minute for short content
    else:
        return (30.0, 60.0)


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
        # Get credits skip ranges
        start_skip, end_skip = get_credits_skip(duration)
        
        # Adjust duration for credits
        if start_skip > 0 and duration > start_skip:
            duration -= start_skip
        if end_skip > 0 and duration > end_skip:
            duration -= end_skip
            
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


def detect_black_bars(input_path: Path, config: Dict[str, str],
                     stream_info: Optional[VideoStreamInfo] = None) -> Optional[CropInfo]:
    """Detect black bars in video.

    Args:
        input_path: Path to input video file
        config: Configuration dictionary with FFmpeg paths
        stream_info: Optional video stream info for HDR-aware threshold

    Returns:
        CropInfo if black bars detected, None if error
    """
    try:
        # Get video duration
        cmd = [
            config.get('ffprobe', 'ffprobe'),
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            str(input_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        duration = float(data['format'].get('duration', 0))

        if duration <= 0:
            logger = logging.getLogger(__name__)
            logger.warning("Invalid duration")
            return None

        # Sample frames for black bar detection
        cmd = [
            config.get('ffmpeg', 'ffmpeg'),
            '-i', str(input_path),
            '-vf', 'cropdetect',
            '-frames:v', '100',
            '-f', 'null',
            '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse crop detection output
        crop_values = []
        for line in result.stderr.splitlines():
            if 'crop=' in line:
                try:
                    crop_str = line.split('crop=')[1].strip()
                    w, h, x, y = map(int, crop_str.split(':'))
                    crop_values.append((w, h, x, y))
                except (ValueError, IndexError):
                    continue

        if not crop_values:
            # No crop values detected
            return None

        # Use most common crop values
        from collections import Counter
        most_common = Counter(crop_values).most_common(1)[0][0]
        w, h, x, y = most_common

        # Check if cropping is actually needed
        min_crop = 10  # Minimum pixels to consider cropping
        if x < min_crop and y < min_crop:
            return CropInfo(x=0, y=0, width=0, height=0, enabled=False)

        # Return crop info if black bars detected
        return CropInfo(x=x, y=y, width=w, height=h, enabled=True)

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"Crop detection failed: {e}")
        return None
