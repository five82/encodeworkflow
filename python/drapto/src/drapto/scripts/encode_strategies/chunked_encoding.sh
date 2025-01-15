#!/usr/bin/env bash

###################
# Chunked Encoding Strategy
###################

source "${SCRIPT_DIR}/utils/formatting.sh"

# Validate video segments
validate_segments() {
    print_check "Validating segments..."
    local dir="$1"
    local min_file_size=1024  # 1KB minimum file size

    local segment_count
    segment_count=$(find "$dir" -name "*.mkv" -type f | wc -l)
    [[ $segment_count -lt 1 ]] && error "No segments found in $dir"

    local invalid_segments=0
    while IFS= read -r -d $'\0' segment; do
        local file_size
        file_size=$(stat -f%z "$segment" 2>/dev/null || stat -c%s "$segment")
        
        if [[ $file_size -lt $min_file_size ]] || ! "${FFPROBE}" -v error "$segment" >/dev/null 2>&1; then
            print_warning "Invalid segment found: $segment"
            ((invalid_segments++))
        fi
    done < <(find "$dir" -name "*.mkv" -type f -print0)

    [[ $invalid_segments -gt 0 ]] && error "Found $invalid_segments invalid segments"
    print_success "Successfully validated $segment_count segments"
}

# Segment video into chunks
segment_video() {
    print_check "Segmenting video..."
    local input_file="$1"
    local output_dir="$2"

    mkdir -p "$output_dir"

    "${FFMPEG}" -hide_banner -loglevel error -i "$input_file" \
        -c:v copy \
        -an \
        -f segment \
        -segment_time "$SEGMENT_LENGTH" \
        -reset_timestamps 1 \
        "${output_dir}/%04d.mkv"

    validate_segments "$output_dir"
}

# Encode video segments using ab-av1
encode_segments() {
    local input_dir="$1"
    local output_dir="$2"
    local target_vmaf="$3"
    local disable_crop="$4"
    local crop_filter="$5"

    # Check if GNU Parallel is installed
    if ! check_parallel_installation; then
        error "Cannot proceed with parallel encoding without GNU Parallel"
        return 1
    fi

    # Create output directory if it doesn't exist
    mkdir -p "$output_dir"

    # Create a temporary file to store segment encoding commands
    local cmd_file=$(mktemp)
    
    # Build the command list
    local segment_count=0
    for segment in "$input_dir"/*.mkv; do
        if [[ -f "$segment" ]]; then
            local segment_name=$(basename "$segment")
            local output_segment="${output_dir}/${segment_name}"
            
            # Skip if output segment already exists and has non-zero size
            if [[ -f "$output_segment" ]] && [[ -s "$output_segment" ]]; then
                print_check "Segment already encoded successfully: ${segment_name}"
                continue
            fi

            # Only pass crop filter if it's not empty
            local vfilter_args=""
            if [[ -n "$crop_filter" ]]; then
                vfilter_args="--vfilter $crop_filter"
            fi

            # Build the encoding command
            echo "encode_single_segment '$segment' '$output_segment' '$target_vmaf' '$vfilter_args'" >> "$cmd_file"
            ((segment_count++))
        fi
    done

    if [[ $segment_count -eq 0 ]]; then
        error "No segments found to encode in $input_dir"
        rm "$cmd_file"
        return 1
    fi

    # Define the single segment encoding function
    encode_single_segment() {
        local segment="$1"
        local output_segment="$2"
        local target_vmaf="$3"
        local vfilter_args="$4"
        
        # First attempt with default settings
        if ab-av1 auto-encode \
            --input "$segment" \
            --output "$output_segment" \
            --encoder libsvtav1 \
            --min-vmaf "$target_vmaf" \
            --preset "$PRESET" \
            --svt "tune=0:film-grain=0:film-grain-denoise=0" \
            --keyint 10s \
            --samples "$VMAF_SAMPLE_COUNT" \
            --sample-duration "${VMAF_SAMPLE_LENGTH}s" \
            --vmaf "n_subsample=8:pool=harmonic_mean" \
            $vfilter_args \
            --quiet; then
            return 0
        fi
        
        # Second attempt with more samples
        if ab-av1 auto-encode \
            --input "$segment" \
            --output "$output_segment" \
            --encoder libsvtav1 \
            --min-vmaf "$target_vmaf" \
            --preset "$PRESET" \
            --svt "tune=0:film-grain=0:film-grain-denoise=0" \
            --keyint 10s \
            --samples 6 \
            --sample-duration "2s" \
            --vmaf "n_subsample=8:pool=harmonic_mean" \
            $vfilter_args \
            --quiet; then
            return 0
        fi
        
        # Final attempt with lower VMAF target
        local lower_vmaf=$((target_vmaf - 2))
        if ab-av1 auto-encode \
            --input "$segment" \
            --output "$output_segment" \
            --encoder libsvtav1 \
            --min-vmaf "$lower_vmaf" \
            --preset "$PRESET" \
            --svt "tune=0:film-grain=0:film-grain-denoise=0" \
            --keyint 10s \
            --samples 6 \
            --sample-duration "2s" \
            --vmaf "n_subsample=8:pool=harmonic_mean" \
            $vfilter_args \
            --quiet; then
            return 0
        fi
        
        error "Failed to encode segment after all attempts: $(basename "$segment")"
        return 1
    }
    export -f encode_single_segment
    export -f print_check
    export -f error
    export PRESET
    export VMAF_SAMPLE_COUNT
    export VMAF_SAMPLE_LENGTH

    # Use GNU Parallel to process segments
    # --jobs determines how many parallel jobs to run (0 means number of CPU cores)
    # --halt soon,fail=1 stops all jobs if any job fails
    # --no-notice suppresses citation notice
    # --line-buffer ensures output lines are not mixed
    if ! parallel --no-notice --line-buffer --halt soon,fail=1 --jobs 0 :::: "$cmd_file"; then
        rm "$cmd_file"
        return 1
    fi

    rm "$cmd_file"
    return 0
}
