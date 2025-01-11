"""Black bar detection utilities."""

import json
from pathlib import Path
import ffmpeg
from typing import List, Optional, Tuple

from loguru import logger

from drapto.core.video.types import VideoStreamInfo, CropInfo
from drapto.core.video.errors import BlackBarDetectionError, CropValidationError


def _get_black_level(input_path: Path, is_hdr: bool = False) -> int:
    """Get black level for crop detection."""
    if not is_hdr:
        return 16  # Default SDR black level

    try:
        # Run FFmpeg black frame detection
        stream = ffmpeg.input(str(input_path))
        stream = ffmpeg.filter(stream, 'blackdetect', d=0)
        logger.debug("Running FFmpeg blackdetect filter")
        out, err = (
            ffmpeg.output(stream, 'pipe:', format='null')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.debug("FFmpeg run completed")
        
        # Parse black levels from stderr
        levels = []
        for line in err.decode().splitlines():
            if 'black_level' in line:
                try:
                    level = int(line.split(':')[1].strip())
                    levels.append(level)
                except (IndexError, ValueError):
                    continue

        if not levels:
            logger.warning("No black levels detected, using default HDR black level")
            return 128  # Default HDR black level

        # Use ~1.5x the average of detected levels
        avg_level = sum(levels) / len(levels)
        return int(avg_level * 1.5)

    except ffmpeg.Error:
        logger.warning("Failed to detect black level, using default HDR black level")
        return 128  # Default HDR black level on error


def get_credits_skip(duration: float) -> float:
    """Calculate how many seconds to skip from the end to avoid credits."""
    if duration < 300:  # Less than 5 minutes
        return 0.0
    elif duration < 1200:  # Less than 20 minutes
        return 30.0
    elif duration < 3600:  # Less than 1 hour
        return 60.0
    else:
        return 180.0


def _get_crop_samples(input_path: Path, duration: float,
                     black_threshold: int,
                     original_width: int, original_height: int) -> List[Tuple[int, int, int, int]]:
    """Get crop samples from the video."""
    try:
        # Calculate sample points
        skip = get_credits_skip(duration)
        duration = max(0, duration - skip)
        
        # Run cropdetect filter
        stream = ffmpeg.input(str(input_path))
        stream = ffmpeg.filter(stream, 'cropdetect', limit=black_threshold)
        logger.debug("Running FFmpeg cropdetect filter")
        out, err = (
            ffmpeg.output(stream, 'pipe:', format='null')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.debug("FFmpeg run completed")

        # Parse crop values
        samples = []
        for line in err.decode().splitlines():
            if 'crop=' in line:
                try:
                    crop_str = line.split('crop=')[1].strip()
                    w, h, x, y = map(int, crop_str.split(':'))
                    if all(v >= 0 for v in (w, h, x, y)) and w <= original_width and h <= original_height:
                        samples.append((w, h, x, y))
                except (IndexError, ValueError):
                    continue

        return samples

    except ffmpeg.Error as e:
        logger.warning(f"Failed to get crop samples: {e}")
        return []


def detect_black_bars(input_path: Path, config: dict,
                     info: Optional[VideoStreamInfo] = None) -> Optional[CropInfo]:
    """Detect black bars in video and return crop parameters."""
    if not input_path.exists():
        logger.warning(f"Input file does not exist: {input_path}")
        return None

    try:
        # Get video info if not provided
        if info is None:
            probe = ffmpeg.probe(str(input_path))
            video_stream = next(
                s for s in probe['streams'] if s['codec_type'] == 'video'
            )
            info = VideoStreamInfo(
                width=int(video_stream['width']),
                height=int(video_stream['height']),
                is_hdr=False,  # Default to SDR if not provided
                frame_rate=eval(video_stream['r_frame_rate'])
            )

        # Get video duration
        probe = ffmpeg.probe(str(input_path))
        duration = float(probe['format']['duration'])
        if duration <= 0:
            logger.warning("Invalid video duration")
            return None

        # Get black level threshold
        black_threshold = _get_black_level(input_path, info.is_hdr)

        # Get crop samples
        samples = _get_crop_samples(input_path, duration, black_threshold,
                                  info.width, info.height)
        if not samples:
            logger.warning("No valid crop values found")
            return None

        # Use most common crop values
        from collections import Counter
        counter = Counter(samples)
        w, h, x, y = counter.most_common(1)[0][0]

        # Validate crop values
        if w == info.width and h == info.height:
            return CropInfo(enabled=False)

        # Create crop info
        return CropInfo(
            enabled=True,
            width=w,
            height=h,
            x=x,
            y=y
        )

    except ffmpeg.Error as e:
        logger.warning(f"FFmpeg error: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error: {e}")
        return None
