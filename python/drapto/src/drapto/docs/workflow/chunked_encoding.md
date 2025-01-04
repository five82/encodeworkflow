# Chunked Encoding Technical Details

## Overview
This document details the technical implementation of the chunked encoding path, which is used for all non-Dolby Vision content.

## 1. Segmentation Process

### Work Directory Structure
```
work_dir/
├── segments/
│   ├── segment_000.mkv
│   ├── segment_001.mkv
│   └── segment_NNN.mkv
├── encoded/
│   ├── segment_000.mkv
│   ├── segment_001.mkv
│   └── segment_NNN.mkv
└── segment_list.txt
```

### Segmentation Steps
1. **Keyframe Analysis**
   ```bash
   ffprobe -select_streams v:0 -show_frames -show_entries frame=key_frame,pkt_pts_time \
     -of csv=p=0 input.mkv
   ```

2. **Segment Creation**
   ```bash
   ffmpeg -i input.mkv -c copy -f segment \
     -segment_time $duration \
     -segment_start_number 0 \
     -reset_timestamps 1 \
     -segment_format mkv \
     segments/segment_%03d.mkv
   ```

## 2. Parallel Encoding

### ab-av1 Configuration
```bash
# Per-segment encoding command
ab-av1 auto-encode \
  --input segment.mkv \
  --output encoded_segment.mkv \
  --encoder libsvtav1 \
  --min-vmaf ${target_vmaf} \
  --preset ${preset} \
  --svt ${svt_params} \
  --keyint 10s \
  --samples ${vmaf_samples} \
  --sample-duration ${sample_duration}s \
  --vmaf n_subsample=8:pool=harmonic_mean
```

### GNU Parallel Implementation
```bash
# Parallel processing command
parallel --jobs ${cpu_count} \
  --bar \
  --eta \
  encode_single_segment {} ::: segments/*.mkv
```

### Resource Management
- Dynamic CPU allocation
- Memory monitoring
- Disk space tracking
- Progress reporting

## 3. Validation Steps

### Per-Segment Validation
1. **Duration Check**
   ```bash
   ffprobe -v error -show_entries format=duration \
     -of default=noprint_wrappers=1:nokey=1 segment.mkv
   ```

2. **Frame Integrity**
   ```bash
   ffmpeg -v error -i segment.mkv -f null - 2>&1
   ```

3. **Stream Properties**
   - Codec parameters
   - Color space
   - Frame rate
   - Resolution

### Concatenation Validation
1. **Timestamp Continuity**
2. **Stream Consistency**
3. **Quality Metrics**

## 4. Error Recovery

### Segment Failures
1. **Detection**
   - Encoding errors
   - Validation failures
   - Resource exhaustion

2. **Recovery Actions**
   - Segment re-encoding
   - Parameter adjustment
   - Resource reallocation

### Process Recovery
1. **Checkpoint System**
   - Segment completion tracking
   - Progress persistence
   - State recovery

2. **Cleanup Procedures**
   - Temporary file removal
   - Resource release
   - State reset

## 5. Performance Optimization

### CPU Utilization
- Worker count calculation
- Load balancing
- Priority management

### Memory Management
- Per-process limits
- Shared memory usage
- Cache optimization

### Storage Optimization
- Cleanup strategies
- Space monitoring
- I/O optimization
