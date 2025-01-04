# Video Encoding Workflow

## Overview

Drapto supports two distinct encoding paths:
1. **Dolby Vision Path**: For content with Dolby Vision metadata
2. **Chunked Encoding Path**: For all other content

The path selection is automatic based on Dolby Vision detection. The chunked encoding path is the default and preferred method, but Dolby Vision content must use the Dolby Vision path due to technical limitations with chunked encoding of Dolby Vision content.

## Common Processing Steps

Both paths share these initial steps:
1. **Input Validation**
   - File existence and permissions
   - Format compatibility
   - Stream analysis

2. **Audio Processing**
   - Audio stream extraction
   - Opus encoding
   - Channel layout preservation
   - This process is identical for both paths to maintain consistency

## Audio Processing

Both paths use the same audio processing workflow to maintain consistency:

1. **Stream Analysis**
   - Extract stream information
   - Detect channel layout
   - Analyze bitrate requirements

2. **Audio Configuration**
   ```python
   # Bitrate selection based on channels
   bitrate_map = {
       1: "64k",    # Mono
       2: "96k",    # Stereo
       6: "192k",   # 5.1
       8: "256k"    # 7.1
   }
   ```

3. **Encoding Process**
   - Convert to Opus format
   - Preserve channel layout
   - Maintain synchronization
   - Example command:
     ```bash
     ffmpeg -i input.mkv \
       -c:a libopus \
       -b:a ${bitrate} \
       -channel_layout ${layout} \
       -vn output.opus
     ```

4. **Validation**
   - Check stream count
   - Verify channel layout
   - Validate bitrate
   - Ensure sync

## Quality Settings

### Resolution-Based Configuration
```bash
# Default quality settings for different resolutions
CRF_SD=25   # For width <= 1280 (720p)
CRF_HD=25   # For width <= 1920 (1080p)
CRF_UHD=29  # For width > 1920 (4K+)

# Default preset and pixel format
PRESET=6
PIX_FMT="yuv420p10le"  # 10-bit for HDR compatibility
```

### Chunked Encoding Path (ab-av1)
```bash
# ab-av1 auto-encode settings
ab-av1 auto-encode \
    --input "$segment" \
    --output "$output_segment" \
    --encoder libsvtav1 \
    --min-vmaf "$target_vmaf" \  # Default: 93
    --preset "$PRESET" \         # Default: 6
    --svt "tune=0:film-grain=0:film-grain-denoise=0" \
    --keyint 10s \
    --samples "$VMAF_SAMPLE_COUNT" \      # Default: 3
    --sample-duration "${VMAF_SAMPLE_LENGTH}s" \  # Default: 1s
    --vmaf "n_subsample=8:pool=harmonic_mean" \
    --quiet
```

### Dolby Vision Path (FFmpeg)
```bash
# FFmpeg with SVT-AV1 settings
ffmpeg -i "$input_file" \
    -c:v libsvtav1 \
    -preset "$PRESET" \
    -crf "$crf" \
    -svtav1-params "tune=0:film-grain=0:film-grain-denoise=0" \
    -dolbyvision true \
    -pix_fmt yuv420p10le \
    "$output_file"
```

Key differences between paths:
1. **Dolby Vision Path**
   - Uses direct FFmpeg encoding
   - CRF-based rate control
   - Fixed preset and pixel format
   - Dolby Vision metadata preservation

2. **Chunked Encoding Path**
   - Uses ab-av1 for quality-targeted encoding
   - VMAF-based rate control
   - Configurable sample count and duration
   - Parallel segment processing

Common settings for both paths:
- SVT-AV1 encoder
- Preset 6 (balanced speed/quality)
- 10-bit pixel format
- Film grain synthesis disabled
- Quality-focused tuning (tune=0)

### Hardware Acceleration
```bash
# Check for hardware acceleration support
check_hardware_acceleration() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Check for macOS VideoToolbox support
        if "${FFMPEG}" -hide_banner -hwaccels | grep -q videotoolbox; then
            echo "Found VideoToolbox hardware acceleration"
            export HW_ACCEL="videotoolbox"
            return 0
        fi
    fi

    # No supported hardware acceleration found
    echo "No supported hardware acceleration found, using software decoding"
    export HW_ACCEL="none"
    return 1
}

# Configure hardware acceleration options
configure_hw_accel_options() {
    case "${HW_ACCEL}" in
        "videotoolbox")
            hw_options="-hwaccel videotoolbox"
            ;;
        *)
            hw_options=""
            ;;
    esac
}
```

Our implementation currently supports:
1. **macOS VideoToolbox**
   - Automatic detection
   - Hardware-accelerated decoding
   - Used when available on macOS systems

2. **Software Fallback**
   - Default when no hardware acceleration is available
   - Pure CPU-based processing
   - Compatible with all platforms

Note: While VAAPI support may be added in the future, it is not currently implemented in our codebase.

## Dolby Vision Path

Used exclusively for content containing Dolby Vision metadata.

### Process Flow
1. **Detection**
   - Analyze input for Dolby Vision metadata
   - Validate Dolby Vision profile compatibility

2. **Audio Processing**
   - Extract audio streams
   - Convert to Opus format with adaptive bitrate:
     ```bash
     # Bitrate selection based on channels
     mono:  64k   (1 channel)
     stereo: 128k (2 channels)
     5.1:    256k (6 channels)
     7.1:    384k (8 channels)
     ```
   - Preserve original channel layout
   - Validate encoded audio streams

3. **Video Encoding**
   - Uses FFmpeg with SVT-AV1 encoder
   - Direct single-pass encoding
   - Preserves Dolby Vision metadata
   - Example command:
     ```bash
     ffmpeg -i input.mkv \
       -c:v libsvtav1 \
       -preset ${preset} \
       ${svt_params} \
       -pix_fmt yuv420p10le \
       -dolbyvision true \
       output.mkv
     ```

4. **Track Muxing**
   - Copy video track from encoded file
   - Copy audio track from Opus encode
   - Copy subtitles from original file
   - Copy chapters from original file
   - Copy attachments from original file
   - Example command:
     ```bash
     ffmpeg -i video.mkv -i audio.opus -i original.mkv \
       -map 0:v:0 \  # Video from encoded file
       -map 1:a? \   # Audio from opus encode
       -map 2:s? \   # Subtitles from original
       -map 2:t? \   # Attachments from original
       -c copy \
       output.mkv
     ```

5. **Validation**
   - Verify Dolby Vision metadata preservation
   - Check audio stream integrity
   - Validate subtitle tracks
   - Verify chapter markers
   - Check output file integrity

## Chunked Encoding Path

Default path for all non-Dolby Vision content.

### Process Flow
1. **Audio Processing**
   - Same process as Dolby Vision path
   - Extract and encode to Opus
   - Validate encoded audio

2. **Segmentation**
   - Split video into chunks at keyframes
   - Preserve frame accuracy
   - Maintain metadata consistency
   - Audio processed separately

3. **Parallel Encoding**
   - Uses ab-av1 for chunk encoding
   - SVT-AV1 as the underlying codec
   - GNU Parallel for parallel processing
   - Example command per chunk:
     ```bash
     ab-av1 auto-encode \
       --input segment.mkv \
       --output encoded_segment.mkv \
       --encoder libsvtav1 \
       --min-vmaf "$target_vmaf" \
       --preset ${preset} \
       ${svt_params} \
       --keyint 10s
     ```

4. **Validation & Concatenation**
   - Per-chunk integrity checks
   - Frame count verification
   - Stream consistency validation
   - Merge encoded chunks
   - Verify seamless transitions

5. **Track Muxing**
   - Same process as Dolby Vision path
   - Concatenated video track
   - Opus audio track
   - Original subtitles and chapters
   - Original attachments

## Validation Process

### Common Validation Steps
1. **Dependency Checks**
   - FFmpeg availability
   - FFprobe availability
   - GNU Parallel (for chunked encoding)
   - ab-av1 (for chunked encoding)

2. **Input Validation**
   - File existence
   - Format compatibility
   - Stream analysis
   - Permission checks

3. **Output Validation**
   - File size verification
   - Duration match
   - Stream count check
   - Codec verification

### Dolby Vision Path Validation
1. **DV Metadata**
   - Profile verification
   - Level verification
   - Color space check

2. **Stream Properties**
   - Resolution match
   - Frame rate match
   - HDR metadata

### Chunked Encoding Validation
1. **Segment Validation**
   - Duration consistency
   - Frame alignment
   - Stream properties
   - Size verification

2. **Concatenation Check**
   - Stream continuity
   - Frame transitions
   - Metadata consistency

### Error Recovery
1. **Segment Failures**
   - Individual retry
   - Parameter adjustment
   - Skip on threshold

2. **Process Recovery**
   - Checkpoint system
   - State restoration
   - Resource cleanup

## Final Steps

Both paths conclude with these steps:

1. **Muxing**
   - Combine encoded video
   - Add processed audio
   - Include subtitles if present
   - Preserve chapters if present

2. **Final Validation**
   - Complete file integrity check
   - Stream property verification
   - Metadata validation

## Resource Management

- Both paths use dedicated work directories
- Temporary files are cleaned up after processing
- Resource limits are enforced per encoding type
- Progress monitoring and logging for both paths

## Error Handling

- Path-specific error recovery
- Detailed error reporting
- Cleanup on failure
- Validation failure handling

## Performance Considerations

### Dolby Vision Path
- Single-process encoding
- Higher memory usage
- Limited parallelization
- Preserves all metadata

### Chunked Encoding Path
- Parallel processing
- Lower per-process memory usage
- Better CPU utilization
- Faster for most content
