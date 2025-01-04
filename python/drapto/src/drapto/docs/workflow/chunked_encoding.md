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

1. **Pre-encode Validation**
   ```bash
   validate_segments() {
       local dir="$1"
       local min_file_size=1024  # 1KB minimum
       
       # Check segment count
       local segment_count
       segment_count=$(find "$dir" -name "*.mkv" -type f | wc -l)
       [[ $segment_count -lt 1 ]] && error "No segments found in $dir"
       
       # Validate each segment
       local invalid_segments=0
       while IFS= read -r -d $'\0' segment; do
           # Check file size and integrity
           local file_size=$(stat -f%z "$segment")
           if [[ $file_size -lt $min_file_size ]] || \
              ! "${FFPROBE}" -v error "$segment" >/dev/null 2>&1; then
               print_warning "Invalid segment: $segment"
               ((invalid_segments++))
           fi
       done < <(find "$dir" -name "*.mkv" -type f -print0)
   }
   ```

2. **Progressive Retry Strategy**
   ```bash
   encode_single_segment() {
       local segment="$1"
       local output_segment="$2"
       local target_vmaf="$3"
       local vfilter_args="$4"
       
       # First attempt: Default settings
       if ab-av1 auto-encode \
           --input "$segment" \
           --output "$output_segment" \
           --min-vmaf "$target_vmaf" \
           --preset "$PRESET" \
           --samples "$VMAF_SAMPLE_COUNT" \
           --sample-duration "${VMAF_SAMPLE_LENGTH}s" \
           $vfilter_args; then
           return 0
       fi
       
       # Second attempt: More samples for better accuracy
       if ab-av1 auto-encode \
           --input "$segment" \
           --output "$output_segment" \
           --min-vmaf "$target_vmaf" \
           --preset "$PRESET" \
           --samples 6 \
           --sample-duration "2s" \
           $vfilter_args; then
           return 0
       fi
       
       # Final attempt: Lower VMAF target
       local lower_vmaf=$((target_vmaf - 2))
       if ab-av1 auto-encode \
           --input "$segment" \
           --output "$output_segment" \
           --min-vmaf "$lower_vmaf" \
           --preset "$PRESET" \
           --samples 6 \
           --sample-duration "2s" \
           $vfilter_args; then
           return 0
       fi
       
       error "Failed to encode segment after all attempts: $(basename "$segment")"
       return 1
   }
   ```

3. **Parallel Processing with Failure Handling**
   ```bash
   encode_segments() {
       # Create output directory
       mkdir -p "$output_dir"
       
       # Process each segment
       for segment in "$input_dir"/*.mkv; do
           local output_segment="${output_dir}/$(basename "$segment")"
           
           # Skip successful segments
           if [[ -f "$output_segment" ]] && [[ -s "$output_segment" ]]; then
               print_check "Already encoded: ${segment_name}"
               continue
           fi
           
           # Add to parallel queue
           echo "encode_single_segment '$segment' '$output_segment' \
                '$target_vmaf' '$vfilter_args'" >> "$cmd_file"
       done
       
       # Run parallel jobs with failure handling
       parallel --no-notice --line-buffer \
           --halt soon,fail=1 --jobs 0 :::: "$cmd_file"
   }
   ```

Key features of our retry strategy:
1. **Progressive Enhancement**:
   - First try: Default settings with configured samples
   - Second try: Increased samples (6) and longer duration (2s)
   - Final try: Lower VMAF target (-2) with increased samples

2. **Failure Detection**:
   - Size validation (minimum 1KB)
   - File integrity check using ffprobe
   - Segment count verification
   - Non-zero output file check

3. **Parallel Processing Safety**:
   - `--halt soon,fail=1`: Stop all jobs on first failure
   - `--line-buffer`: Prevent output mixing
   - Skip already successful segments
   - Proper cleanup on any failure

4. **Resource Management**:
   - Temporary file cleanup
   - Export necessary functions and variables
   - Proper GNU Parallel configuration
   - Automatic CPU core detection

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

## 6. Resource Monitoring

### System Resources
1. **CPU Monitoring**
   ```python
   # Get available CPU count
   cpu_count = len(os.sched_getaffinity(0))
   
   # Reserve cores for system
   worker_count = max(1, cpu_count - 2)
   ```

2. **Memory Tracking**
   ```python
   # Per-process memory limit
   memory_per_process = total_memory // worker_count
   
   # Set ulimit for child processes
   resource.setrlimit(
       resource.RLIMIT_AS,
       (memory_per_process, memory_per_process)
   )
   ```

3. **Storage Management**
   ```python
   # Required space calculation
   required_space = input_size * 1.5  # 50% buffer
   
   # Cleanup trigger
   cleanup_threshold = 0.9  # 90% disk usage
   ```

### Process Management
1. **Worker Control**
   ```bash
   # GNU Parallel job control
   parallel --jobs ${worker_count} \
     --memfree ${memory_per_process} \
     --load ${max_load} \
     encode_single_segment
   ```

2. **Progress Tracking**
   - Per-segment progress
   - Overall completion
   - Time estimation
   - Resource usage

3. **Error Handling**
   - Process timeout
   - Resource exhaustion
   - I/O errors
   - Signal handling
