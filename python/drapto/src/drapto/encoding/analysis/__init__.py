"""Video analysis package.

This package provides functionality for analyzing video streams, including:
- HDR format detection
- Black bar detection
- Quality settings selection
"""

from .video import (
    detect_dolby_vision,
    detect_black_bars,
    detect_black_level,
    detect_hdr,
    VideoAnalysisError,
    HDRDetectionError,
    BlackBarDetectionError,
    FFmpegError,
    MediaInfoError
)
