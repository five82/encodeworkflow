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
        logger.debug("Using default SDR black level: 16")
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
        logger.debug("FFmpeg blackdetect completed")
        
        # Parse black levels from stderr
        levels = []
        for line in err.decode().splitlines():
            if 'black_level' in line:
                try:
                    level = int(line.split(':')[1].strip())
                    levels.append(level)
                    logger.debug(f"Detected black level: {level}")
                except (IndexError, ValueError):
                    logger.warning(f"Failed to parse black level from line: {line}")
                    continue

        if not levels:
            logger.warning("No black levels detected in HDR content, using default level: 128")
            return 128  # Default HDR black level

        # Use ~1.5x the average of detected levels
        avg_level = sum(levels) / len(levels)
        adjusted_level = int(avg_level * 1.5)
        logger.info(f"Using adjusted black level for HDR: {adjusted_level} (average of {len(levels)} samples)")
        return adjusted_level

    except ffmpeg.Error as e:
        logger.warning(f"Failed to detect black level: {e.stderr.decode() if e.stderr else str(e)}")
        logger.warning("Using default HDR black level: 128")
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
        logger.debug(f"Analyzing video for crop detection (duration: {duration}s, threshold: {black_threshold})")
        
        # Run cropdetect filter
        stream = ffmpeg.input(str(input_path))
        stream = ffmpeg.filter(stream, 'cropdetect', limit=black_threshold)
        logger.debug("Running FFmpeg cropdetect filter")
        out, err = (
            ffmpeg.output(stream, 'pipe:', format='null')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.debug("FFmpeg cropdetect completed")

        # Parse crop values
        samples = []
        invalid_samples = 0
        for line in err.decode().splitlines():
            if 'crop=' in line:
                try:
                    crop_str = line.split('crop=')[1].strip()
                    w, h, x, y = map(int, crop_str.split(':'))
                    if all(v >= 0 for v in (w, h, x, y)) and w <= original_width and h <= original_height:
                        samples.append((w, h, x, y))
                        logger.debug(f"Valid crop sample: w={w} h={h} x={x} y={y}")
                    else:
                        invalid_samples += 1
                        logger.debug(f"Invalid crop values detected: w={w} h={h} x={x} y={y}")
                except (IndexError, ValueError):
                    invalid_samples += 1
                    logger.warning(f"Failed to parse crop values from line: {line}")
                    continue

        logger.info(f"Collected {len(samples)} valid crop samples ({invalid_samples} invalid samples)")
        return samples

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg cropdetect failed: {e.stderr.decode() if e.stderr else str(e)}")
        return []


def detect_black_bars(input_path: Path, config: dict,
                     info: Optional[VideoStreamInfo] = None) -> Optional[CropInfo]:
    """Detect black bars in video and return crop parameters."""
    if not input_path.exists():
        logger.error(f"Input file does not exist: {input_path}")
        return None

    try:
        # Get video info if not provided
        if info is None:
            logger.debug("Video info not provided, probing file")
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
            logger.debug(f"Probed video info: {info}")

        # Get video duration
        probe = ffmpeg.probe(str(input_path))
        duration = float(probe['format']['duration'])
        if duration <= 0:
            logger.error(f"Invalid video duration: {duration}")
            return None

        # Get black level threshold
        black_threshold = _get_black_level(input_path, info.is_hdr)
        logger.info(f"Using black level threshold: {black_threshold}")

        # Get crop samples
        samples = _get_crop_samples(input_path, duration, black_threshold,
                                  info.width, info.height)
        if not samples:
            logger.warning("No valid crop samples found")
            return None

        # Use most common crop values
        from collections import Counter
        counter = Counter(samples)
        w, h, x, y = counter.most_common(1)[0][0]
        logger.info(f"Most common crop values: width={w} height={h} x={x} y={y}")

        # Validate crop values
        MIN_CROP_PIXELS = 10  # Don't crop if difference is less than this
        height_diff = info.height - h
        if w == info.width and (height_diff == 0 or height_diff < MIN_CROP_PIXELS):
            logger.info("No significant cropping needed - video has correct dimensions or crop too small")
            return CropInfo(enabled=False)

        # Create crop info
        crop_info = CropInfo(
            enabled=True,
            width=w,
            height=h,
            x=x,
            y=y
        )
        logger.info(f"Detected black bars - crop info: {crop_info}")
        return crop_info

    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error during black bar detection: {e.stderr.decode() if e.stderr else str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during black bar detection: {str(e)}")
        return None
