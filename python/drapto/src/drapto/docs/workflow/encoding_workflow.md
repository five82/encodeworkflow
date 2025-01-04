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
