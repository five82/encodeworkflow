"""Black bar detection and cropping."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from .types import CropInfo, VideoStreamInfo


def get_crop_threshold(stream_info: VideoStreamInfo) -> int:
    """Get crop detection threshold based on HDR status.
    
    Args:
        stream_info: Video stream information
        
    Returns:
        Threshold value for crop detection
    """
    if stream_info.is_hdr:
        return 128  # Higher threshold for HDR content
    return 16  # Standard threshold for SDR content


def get_credits_skip(duration: float) -> Tuple[float, float]:
    """Get credits skip time based on content length.
    
    Args:
        duration: Content duration in seconds
        
    Returns:
        Tuple of (start_time, duration_to_analyze)
    """
    if duration > 3600:  # > 1 hour
        return 60, 180  # Skip first minute, analyze 3 minutes
    elif duration > 1200:  # > 20 minutes
        return 30, 60   # Skip first 30s, analyze 1 minute
    elif duration > 300:  # > 5 minutes
        return 15, 30   # Skip first 15s, analyze 30 seconds
    return 0, min(duration, 30)  # Analyze up to 30 seconds


def detect_black_bars(input_path: Path, config: Dict[str, Any], stream_info: Optional[VideoStreamInfo] = None) -> Optional[CropInfo]:
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
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Get video duration
        duration_cmd = [
            config.get('ffprobe', 'ffprobe'),
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            str(input_path)
        ]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True)
        duration = float(json.loads(duration_result.stdout)['format']['duration'])
        
        # Get analysis start time and duration
        start_time, analyze_duration = get_credits_skip(duration)
        
        # Get crop threshold
        threshold = get_crop_threshold(stream_info) if stream_info else 16
        
        # Run cropdetect filter
        cmd = [
            config.get('ffmpeg', 'ffmpeg'),
            '-ss', str(start_time),
            '-i', str(input_path),
            '-vf', f'cropdetect={threshold}:2:0',  # threshold:round:skip
            '-f', 'null',
            '-t', str(analyze_duration),
            '-'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        # Parse crop values from output
        crops = []
        for line in result.stderr.splitlines():
            if 'crop=' in line:
                crop_part = line.split('crop=')[1].split(' ')[0]
                w, h, x, y = map(int, crop_part.split(':'))
                crops.append((w, h, x, y))
                
        if not crops:
            logger.warning("No crop values detected")
            return None
            
        # Get most common crop values
        crop_counts = {}
        for crop in crops:
            crop_counts[crop] = crop_counts.get(crop, 0) + 1
            
        most_common = max(crop_counts.items(), key=lambda x: x[1])[0]
        w, h, x, y = most_common
        
        # Create crop info
        crop_info = CropInfo(x=x, y=y, width=w, height=h)
        
        # Enable if significant cropping detected
        if x > 0 or y > 0:
            crop_info.enabled = True
            logger.info("Detected crop: %dx%d+%d+%d", w, h, x, y)
            
        return crop_info
        
    except subprocess.CalledProcessError as e:
        logger.error("Crop detection failed: %s", e)
        return None
    except Exception as e:
        logger.error("Crop detection failed: %s", e)
        return None
