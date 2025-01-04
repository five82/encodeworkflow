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
1. **SD (≤1280p)**
   ```python
   {
       "crf": 30,
       "preset": 8,
       "pix_fmt": "yuv420p"
   }
   ```

2. **HD (≤1920p)**
   ```python
   {
       "crf": 32,
       "preset": 8,
       "pix_fmt": "yuv420p"
   }
   ```

3. **UHD (>1920p)**
   ```python
   {
       "crf": 34,
       "preset": 8,
       "pix_fmt": "yuv420p10le"  # 10-bit for HDR
   }
   ```

### SVT-AV1 Parameters
```python
svt_params = {
    "tune": 0,           # Visual quality tuning
    "film-grain": 8,     # Film grain synthesis level
    "keyint": "10s",     # Keyframe interval
    "sc-detection": 1    # Scene change detection
}
```

### Hardware Acceleration
```python
# NVIDIA GPU acceleration
hw_accel_opts = "-hwaccel cuda -hwaccel_output_format cuda"

# CPU-only encoding
hw_accel_opts = None
```

## Dolby Vision Path

Used exclusively for content containing Dolby Vision metadata.

### Process Flow
1. **Detection**
   - Analyze input for Dolby Vision metadata
   - Validate Dolby Vision profile compatibility

2. **Video Encoding**
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
       output.mkv
     ```

3. **Validation**
   - Verify Dolby Vision metadata preservation
   - Check output file integrity
   - Validate stream properties

## Chunked Encoding Path

Default path for all non-Dolby Vision content.

### Process Flow
1. **Segmentation**
   - Split video into chunks at keyframes
   - Preserve frame accuracy
   - Maintain metadata consistency

2. **Parallel Encoding**
   - Uses ab-av1 for chunk encoding
   - SVT-AV1 as the underlying codec
   - GNU Parallel for parallel processing
   - Example command per chunk:
     ```bash
     ab-av1 auto-encode \
       --input segment.mkv \
       --output encoded_segment.mkv \
       --encoder libsvtav1 \
       --preset ${preset} \
       ${svt_params} \
       --keyint 10s
     ```

3. **Validation**
   - Per-chunk integrity checks
   - Frame count verification
   - Stream consistency validation

4. **Concatenation**
   - Merge encoded chunks
   - Verify seamless transitions
   - Final stream validation

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
