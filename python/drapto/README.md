# Drapto

A powerful video encoding workflow automation tool that combines the efficiency of AV1 encoding with intelligent quality control.

## Features

- AV1 encoding with VMAF-based quality control:
  - Uses ab-av1 for regular content
  - Uses SVT-AV1 for Dolby Vision content
- Smart resolution-based encoding:
  - SD (≤720p): CRF 25
  - HD (≤1080p): CRF 25
  - UHD (>1080p): CRF 29
- Automatic black bar detection and cropping
- Chunked encoding for better resource utilization
- Comprehensive audio processing:
  - Opus encoding with channel-based bitrates:
    - Mono: 64k
    - Stereo: 128k
    - 5.1: 256k
    - 7.1: 384k
    - Custom: 48k per channel
- Hardware acceleration:
  - VideoToolbox for Apple Silicon
  - VAAPI for Linux
- Parallel processing using GNU Parallel

## Requirements

### Common Dependencies
- Python 3.8+
- FFmpeg
- FFprobe
- MediaInfo
- GNU Parallel
- ab-av1
- pipx (for installation)

### Python Dependencies
- loguru
- pydantic

### Platform-Specific Dependencies
#### macOS
- Homebrew
- VideoToolbox (for Apple Silicon)

#### Linux
- VAAPI (for hardware acceleration)

## Installation

1. Install system dependencies:

On macOS with Homebrew:
```bash
# Install system dependencies
brew install python ffmpeg mediainfo parallel pipx

# Install ab-av1
brew tap alexheretic/ab-av1
brew install ab-av1
```

On Linux (Fedora):
```bash
# Install system dependencies
sudo dnf install python3 ffmpeg mediainfo parallel pipx
sudo dnf install python3-loguru python3-pydantic

# Install ab-av1 (from source)
cargo install ab-av1
```

2. Install Drapto:
```bash
# Install using pipx (recommended)
pipx install drapto

# Or install in development mode
pipx install -e /path/to/drapto
```

## Usage

Basic usage:
```bash
drapto input.mkv output.mkv
```

Advanced options:
```bash
drapto \
    --target-vmaf 93 \
    --preset 6 \
    --vmaf-sample-count 30 \
    --vmaf-sample-length 2 \
    --working-dir /path/to/workdir \
    --disable-crop \
    --disable-chunked \
    --log-level DEBUG \
    input.mkv output.mkv
```

Process a directory of videos:
```bash
drapto input_dir/ output_dir/
```

## Configuration

All command line options can be configured in a YAML configuration file:

```yaml
# ~/.config/drapto/config.yaml
target_vmaf: 93
preset: 6
vmaf_sample_count: 30
vmaf_sample_length: 2
working_dir: /path/to/workdir  # Optional: override default working directory
disable_crop: false
disable_chunked: false
log_level: INFO
```

### Working Directory

By default, Drapto creates a temporary working directory next to each input file with the pattern `{input_name}_drapto_work/`. This directory contains:
- `segments/` - Video segments for chunked encoding
- `encoded/` - Encoded video segments

You can override this behavior by specifying a custom working directory:
```bash
drapto --working-dir /path/to/workdir input.mkv output.mkv
```

When using a custom working directory, Drapto will create a subdirectory for each input file using the pattern:
`/path/to/workdir/{input_name}/`

## Directory Structure

```
videos/
├── input/     # Input videos
├── output/    # Encoded videos
├── logs/      # Encoding logs
├── segments/  # Temporary segments
└── working/   # Working directory
```

## Notes

- Dolby Vision content is automatically detected and encoded using SVT-AV1 without chunking
- Hardware acceleration is automatically configured based on platform and availability
- Audio tracks are automatically processed with optimal bitrates based on channel count
- All temporary files are automatically cleaned up after encoding
