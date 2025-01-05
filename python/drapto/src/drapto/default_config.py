"""Default configuration values."""

import os
import platform
import shutil
import tempfile
from pathlib import Path


# System paths
SCRIPT_DIR = Path(__file__).parent.parent.parent

# Try to find ffmpeg/ffprobe in $HOME/ffmpeg first, fallback to system
HOME_FFMPEG_DIR = Path.home() / "ffmpeg"
if HOME_FFMPEG_DIR.exists():
    FFMPEG = HOME_FFMPEG_DIR / "ffmpeg"
    FFPROBE = HOME_FFMPEG_DIR / "ffprobe"
    if not FFMPEG.exists() or not FFPROBE.exists():
        FFMPEG = Path(shutil.which("ffmpeg") or "ffmpeg")
        FFPROBE = Path(shutil.which("ffprobe") or "ffprobe")
else:
    FFMPEG = Path(shutil.which("ffmpeg") or "ffmpeg")
    FFPROBE = Path(shutil.which("ffprobe") or "ffprobe")

# Directory structure
SEGMENTS_DIR = Path(os.getenv("SEGMENTS_DIR", tempfile.gettempdir())) / "segments"
ENCODED_SEGMENTS_DIR = Path(os.getenv("ENCODED_SEGMENTS_DIR", tempfile.gettempdir())) / "encoded"

# ab-av1 encoding settings
TARGET_VMAF = 93
PRESET = 6
SEGMENT_LENGTH = 15
VMAF_SAMPLE_LENGTH = 1
VMAF_SAMPLE_COUNT = 3

# ffmpeg SVT-AV1 video encoding settings
PRESET = 6
CRF_SD = 25     # For videos with width <= 1280 (720p)
CRF_HD = 25     # For videos with width <= 1920 (1080p)
CRF_UHD = 29    # For videos with width > 1920 (4K and above)
SVT_PARAMS = "tune=0:film-grain=0:film-grain-denoise=0"
PIX_FMT = "yuv420p10le"

# Hardware acceleration options
HW_ACCEL_OPTS = ""

# Dolby Vision detection flag
IS_DOLBY_VISION = False

# Cropping settings
DISABLE_CROP = False

# Chunked encoding settings
ENABLE_CHUNKED_ENCODING = True

# Resource monitoring settings
MIN_DISK_GB = 50.0  # Minimum free disk space in GB
MAX_CPU_PERCENT = 90.0  # Maximum CPU usage percentage
MAX_MEMORY_PERCENT = 90.0  # Maximum memory usage percentage
DISK_BUFFER_FACTOR = 1.5  # Buffer factor for disk space (input_size * factor)
