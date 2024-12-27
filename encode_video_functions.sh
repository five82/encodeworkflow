#!/usr/bin/env bash

###################
# Video Functions
###################

# Detect if the input file contains Dolby Vision
detect_dolby_vision() {
    echo "Detecting Dolby Vision..."
    local file="$1"

    local is_dv
    is_dv=$(mediainfo "$file" | grep "Dolby Vision" || true)

    if [[ -n "$is_dv" ]]; then
        echo "Dolby Vision detected"
        IS_DOLBY_VISION=true
        return 0
    else
        echo "Dolby Vision not detected. Continuing with standard encoding..."
        return 1
    fi
}

# Detect black bars and return crop values
detect_crop() {
    local input_file="$1"
    local disable_crop="$2"

    if [[ "$disable_crop" == "true" ]]; then
        echo "Crop detection disabled" >&2
        return 0
    fi

    echo "Detecting vertical black bars..." >&2

    # Check if input is HDR
    local is_hdr
    is_hdr=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=color_transfer -of default=noprint_wrappers=1:nokey=1 "$input_file" | grep -i "smpte2084\|arib-std-b67" || true)

    # Adjust cropdetect threshold based on HDR status
    local crop_threshold=16
    if [[ -n "$is_hdr" ]]; then
        echo "HDR content detected, adjusting crop detection threshold" >&2
        crop_threshold=128  # Higher threshold for HDR content
    fi

    # Sample the video at different intervals
    local duration
    duration=$("${FFPROBE}" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$input_file")
    # Convert floating point duration to integer seconds
    duration=$(printf "%.0f" "$duration")
    
    # Skip credits based on content length
    local credits_skip=0
    if [ "$duration" -gt 3600 ]; then
        # Movies (>1 hour): Skip 3 minutes
        credits_skip=180
    elif [ "$duration" -gt 1200 ]; then
        # Long content (>20 minutes): Skip 1 minute
        credits_skip=60
    elif [ "$duration" -gt 300 ]; then
        # Medium content (>5 minutes): Skip 30 seconds
        credits_skip=30
    fi
    # Short content (<5 minutes): Don't skip anything

    if [ "$credits_skip" -gt 0 ]; then
        if [ "$duration" -gt "$credits_skip" ]; then
            duration=$((duration - credits_skip))
            echo "Content duration: ${duration}s, skipping last ${credits_skip}s to avoid end credits" >&2
        fi
    else
        echo "Short content detected (${duration}s), analyzing entire duration" >&2
    fi
    
    local interval=5  # Check every 5 seconds
    local total_samples=$((duration / interval))
    
    # Ensure we check at least 20 samples
    if [ "$total_samples" -lt 20 ]; then
        interval=$((duration / 20))
        [ "$interval" -lt 1 ] && interval=1
        total_samples=20
    fi

    echo "Analyzing video with $total_samples samples at ${interval}s intervals..." >&2

    # Run crop detection with HDR-aware threshold
    local crop_values
    crop_values=$("${FFMPEG}" -hide_banner -i "${input_file}" \
                 -vf "select='lt(t,${duration})*not(mod(t,${interval}))',cropdetect=limit=${crop_threshold}:round=2:reset=1" \
                 -f null - 2>&1 | \
                 awk '/crop/ { print $NF }')

    # Get the original height
    local original_height
    original_height=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "${input_file}")

    # Analyze all crop heights and their frequencies
    echo "Analyzing aspect ratio distribution..." >&2
    local heights_analysis
    heights_analysis=$(echo "$crop_values" | \
        awk -F':' '{print $2}' | \
        sort | uniq -c | sort -nr)

    # Print aspect ratio distribution
    echo "Height distribution (frequency : height):" >&2
    echo "$heights_analysis" >&2

    # Find heights that occur at least 15% of the time
    local actual_samples=$(echo "$heights_analysis" | awk '{sum += $1} END {print sum}')
    local min_frequency=$((actual_samples * 15 / 100))  # 15% threshold
    
    echo "Planned samples: $total_samples" >&2
    echo "Actual samples analyzed: $actual_samples" >&2
    echo "Requiring at least $min_frequency samples (15%) to consider a height value" >&2

    # Get the largest height that occurs frequently
    local target_height
    target_height=$(echo "$heights_analysis" | \
        awk -v min="$min_frequency" -v orig="$original_height" '
        $1 >= min && $2 < orig {
            if (!max || $2 > max) max = $2
            printf "Height %d appears in %d samples (%.1f%%)\n", $2, $1, ($1/total*100) > "/dev/stderr"
        }
        END {
            if (max) print max
        }' total="$actual_samples")

    if [[ -n "$target_height" && "$target_height" -gt 0 ]]; then
        # Get the corresponding crop value for this height
        local crop_line
        crop_line=$(echo "$crop_values" | grep ":${target_height}:" | head -n1)
        
        if [[ -n "$crop_line" ]]; then
            local width height x y
            IFS=':' read -r width height x y <<< "${crop_line#*=}"

            local total_crop=$((original_height - height))
            local min_crop_threshold=20

            if [[ $total_crop -ge $min_crop_threshold ]]; then
                local aspect_ratio_original=$(echo "scale=2; $width/$original_height" | bc)
                local aspect_ratio_cropped=$(echo "scale=2; $width/$height" | bc)
                
                echo "Original aspect ratio: $aspect_ratio_original" >&2
                echo "Cropped aspect ratio: $aspect_ratio_cropped" >&2
                echo "Detected vertical black bars - original height: ${original_height}, cropped height: ${height}" >&2
                echo "Crop will remove $total_crop pixels ($((total_crop/2)) from top and bottom)" >&2
                printf "crop=in_w:%d:%d:%d" "$height" "0" "$y"
                return 0
            fi
        fi
    fi

    echo "No significant consistent vertical black bars detected" >&2
    return 0
}

# Set up video encoding options based on input file
setup_video_options() {
    local input_file="$1"
    local disable_crop="${2:-false}"  # New parameter with default value false

    # Get video width
    local width
    width=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=width -of default=noprint_wrappers=1:nokey=1 "$input_file")

    # Set CRF based on video width
    local crf
    if [ "$width" -le 1280 ]; then
        crf=$CRF_SD
        echo "SD quality detected (width: ${width}px), using CRF ${crf}" >&2
    elif [ "$width" -le 1920 ]; then
        crf=$CRF_HD
        echo "HD quality detected (width: ${width}px), using CRF ${crf}" >&2
    else
        crf=$CRF_UHD
        echo "UHD quality detected (width: ${width}px), using CRF ${crf}" >&2
    fi

    local video_opts=""
    
    # Detect crop values
    local crop_filter
    crop_filter=$(detect_crop "${input_file}" "${disable_crop}")
    
    # Build video filter chain
    local vf_filters="format=${PIX_FMT}"
    if [[ -n "$crop_filter" ]]; then
        vf_filters="${crop_filter},${vf_filters}"
    fi
    
    # Standard software encoding
    video_opts="-vf ${vf_filters} \
        -c:v libsvtav1 \
        -preset ${PRESET} \
        -crf ${crf} \
        -svtav1-params ${SVT_PARAMS}"
    echo "Using standard encoding settings" >&2

    if [[ "$IS_DOLBY_VISION" == "true" ]]; then
        video_opts+=" -dolbyvision true"
        echo "Using Dolby Vision encoding settings" >&2
    fi

    printf "%s" "${video_opts}"
}

# Get sizes of the video and audio streams in a file
get_stream_sizes() {
    local file="$1"
    local video_size=0
    local audio_size=0

    # Create temp directory for demuxed streams
    local temp_dir
    temp_dir=$(mktemp -d)

    # Get video codec and extract
    local video_codec
    video_codec=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$file")

    case "$video_codec" in
        h264) video_ext="h264" ;;
        hevc) video_ext="hevc" ;;
        av1)  video_ext="obu" ;;
        *)    video_ext="mkv" ;;
    esac
    local video_file="${temp_dir}/video.${video_ext}"
    "${FFMPEG}" -v error -i "$file" -map 0:v:0 -c copy "${video_file}"

    # Get audio codec and extract
    local audio_codec
    audio_codec=$("${FFPROBE}" -v error -select_streams a:0 -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$file")

    case "$audio_codec" in
        aac)  audio_ext="aac" ;;
        ac3)  audio_ext="ac3" ;;
        dts)  audio_ext="dts" ;;
        opus) audio_ext="opus" ;;
        *)    audio_ext="mka" ;;
    esac
    local audio_file="${temp_dir}/audio.${audio_ext}"
    "${FFMPEG}" -v error -i "$file" -map 0:a -c copy "${audio_file}"

    # Get sizes if files exist
    if [[ -f "${video_file}" ]]; then
        video_size=$(get_file_size "${video_file}")
    fi

    if [[ -f "${audio_file}" ]]; then
        audio_size=$(get_file_size "${audio_file}")
    fi

    # Cleanup temp files
    rm -rf "${temp_dir}"

    # Return both sizes
    echo "${video_size:-0},${audio_size:-0}"
}

# Print a summary of the encoding process for a single file
print_encoding_summary() {
    local i="$1"
    local time_seconds=${encoding_times[$i]}
    local h=$((time_seconds / 3600))
    local m=$(( (time_seconds % 3600) / 60 ))
    local s=$((time_seconds % 60))

    # Get raw sizes for reduction calculation
    local input_raw=${input_sizes[$i]}
    local output_raw=${output_sizes[$i]}

    # Get stream sizes for input and output
    local input_file="${INPUT_DIR}/${encoded_files[$i]}"
    local output_file="${OUTPUT_DIR}/${encoded_files[$i]}"

    IFS=',' read -r input_video_size input_audio_size <<< "$(get_stream_sizes "$input_file")"
    IFS=',' read -r output_video_size output_audio_size <<< "$(get_stream_sizes "$output_file")"

    # Calculate reduction using the raw byte values
    local reduction
    reduction=$(echo "scale=2; (1 - ($output_raw/$input_raw)) * 100" | bc)

    # Convert all sizes to MB for display
    local input_mb=$(echo "scale=2; $input_raw / 1048576" | bc)
    local output_mb=$(echo "scale=2; $output_raw / 1048576" | bc)
    local input_video_mb=$(echo "scale=2; $input_video_size / 1048576" | bc)
    local input_audio_mb=$(echo "scale=2; $input_audio_size / 1048576" | bc)
    local output_video_mb=$(echo "scale=2; $output_video_size / 1048576" | bc)
    local output_audio_mb=$(echo "scale=2; $output_audio_size / 1048576" | bc)

    echo "${encoded_files[$i]}"
    echo "  Encode time: ${h}h ${m}m ${s}s"
    echo "  Input size:  ${input_mb} MB"
    echo "    - Video:   ${input_video_mb} MB"
    echo "    - Audio:   ${input_audio_mb} MB"
    echo "  Output size: ${output_mb} MB"
    echo "    - Video:   ${output_video_mb} MB"
    echo "    - Audio:   ${output_audio_mb} MB"
    echo "  Reduced by:  ${reduction}%"
    echo "----------------------------------------"
}

# Configure hardware acceleration options
configure_hw_accel_options() {
    local hw_options=""
    
    case "${HW_ACCEL}" in
        "videotoolbox")
            hw_options="-hwaccel videotoolbox"
            ;;
        *)
            hw_options=""
            ;;
    esac
    
    echo "${hw_options}"
} 