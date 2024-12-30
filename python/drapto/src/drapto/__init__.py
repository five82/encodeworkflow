"""Video encoding workflow package."""

from .config import EncodingConfig
from .video_processor import VideoProcessor
from .encoder import VideoEncoder
from .segment_handler import SegmentHandler

__version__ = "0.1.0"

__all__ = [
    "EncodingConfig",
    "VideoProcessor",
    "VideoEncoder",
    "SegmentHandler",
]
