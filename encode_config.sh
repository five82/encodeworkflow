#!/usr/bin/env bash

###################
# Configuration
###################

# Paths (assumes SCRIPT_DIR is set before sourcing this file)
FFMPEG="${SCRIPT_DIR}/ffmpeg"
FFPROBE="${SCRIPT_DIR}/ffprobe"
INPUT_DIR="${SCRIPT_DIR}/videos/input"
OUTPUT_DIR="${SCRIPT_DIR}/videos/output"
LOG_DIR="${SCRIPT_DIR}/videos/logs"

# Encoding settings
PRESET=6
CRF_SD=25     # For videos with width <= 1280 (720p)
CRF_HD=25     # For videos with width <= 1920 (1080p)
CRF_UHD=29    # For videos with width > 1920 (4K and above)
SVT_PARAMS="tune=0:film-grain=0:film-grain-denoise=0"
PIX_FMT="yuv420p10le"

# Hardware acceleration options (will be set during initialization)
HWACCEL_OPTS=""

# Dolby Vision detection flag
IS_DOLBY_VISION=false

# Cropping settings
DISABLE_CROP=false

# Arrays to store encoding information
declare -a encoded_files
declare -a encoding_times
declare -a input_sizes
declare -a output_sizes 