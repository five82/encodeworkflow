#!/usr/bin/env bash

###################
# Video Functions
###################

source "${SCRIPT_DIR}/encode_formatting.sh"

# Detect if the input file contains Dolby Vision
detect_dolby_vision() {
    print_check "Checking for Dolby Vision..."
    local file="$1"

    local is_dv
    is_dv=$(mediainfo "$file" | grep "Dolby Vision" || true)

    if [[ -n "$is_dv" ]]; then
        print_check "Dolby Vision detected"
        IS_DOLBY_VISION=true
        return 0
    else
        print_check "Standard HDR/SDR content detected"
        return 1
    fi
}

# Detect black bars and return crop values
detect_crop() {
    local input_file="$1"
    local disable_crop="$2"

    if [[ "$disable_crop" == "true" ]]; then
        print_check "Crop detection disabled"
        return 0
    fi

    print_check "Analyzing video for black bars..."

    # Check if input is HDR and get color properties
    local color_transfer color_primaries color_space
    color_transfer=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=color_transfer -of default=noprint_wrappers=1:nokey=1 "$input_file")
    color_primaries=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=color_primaries -of default=noprint_wrappers=1:nokey=1 "$input_file")
    color_space=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=color_space -of default=noprint_wrappers=1:nokey=1 "$input_file")

    # Set initial crop threshold
    local crop_threshold=16
    local is_hdr=false

    # Check for various HDR formats
    if [[ "$color_transfer" =~ ^(smpte2084|arib-std-b67|smpte428|bt2020-10|bt2020-12)$ ]] || \
       [[ "$color_primaries" =~ ^(bt2020)$ ]] || \
       [[ "$color_space" =~ ^(bt2020nc|bt2020c)$ ]]; then
        is_hdr=true
        crop_threshold=128
        print_check "HDR content detected, adjusting detection sensitivity"
    fi

    # Get maximum pixel value to help determine black level
    if [[ "$is_hdr" == "true" ]]; then
        # Sample a few frames to find the typical black level
        local black_level
        black_level=$("${FFMPEG}" -hide_banner -i "${input_file}" \
            -vf "select='eq(n,0)+eq(n,100)+eq(n,200)',blackdetect=d=0:pic_th=0.1" \
            -f null - 2>&1 | \
            grep "black_level" | \
            awk -F: '{sum += $2; count++} END {if(count>0) print int(sum/count); else print 128}')

        # Adjust threshold based on measured black level
        crop_threshold=$((black_level * 3 / 2))  # Multiply by 1.5 using integer arithmetic
    fi

    # Ensure threshold is within reasonable bounds
    if [ "$crop_threshold" -lt 16 ]; then
        crop_threshold=16
    elif [ "$crop_threshold" -gt 256 ]; then
        crop_threshold=256
    fi

    # Sample the video at different intervals
    local duration
    duration=$("${FFPROBE}" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$input_file")
    duration=$(printf "%.0f" "$duration")
    
    # Skip credits based on content length
    local credits_skip=0
    if [ "$duration" -gt 3600 ]; then
        credits_skip=180  # Movies (>1 hour): Skip 3 minutes
    elif [ "$duration" -gt 1200 ]; then
        credits_skip=60   # Long content (>20 minutes): Skip 1 minute
    elif [ "$duration" -gt 300 ]; then
        credits_skip=30   # Medium content (>5 minutes): Skip 30 seconds
    fi

    if [ "$credits_skip" -gt 0 ]; then
        if [ "$duration" -gt "$credits_skip" ]; then
            duration=$((duration - credits_skip))
        fi
    fi
    
    local interval=5  # Check every 5 seconds
    local total_samples=$((duration / interval))
    
    # Ensure we check at least 20 samples
    if [ "$total_samples" -lt 20 ]; then
        interval=$((duration / 20))
        [ "$interval" -lt 1 ] && interval=1
        total_samples=20
    fi

    print_check "Analyzing $(print_stat "${total_samples}") frames for black bars..."

    # Get the original dimensions first
    local original_width original_height
    original_width=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=width -of default=noprint_wrappers=1:nokey=1 "${input_file}")
    original_height=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=height -of default=noprint_wrappers=1:nokey=1 "${input_file}")

    # Then run crop detection with HDR-aware threshold
    local crop_values
    crop_values=$("${FFMPEG}" -hide_banner -i "${input_file}" \
                 -vf "select='not(mod(n,30))',cropdetect=limit=${crop_threshold}:round=2:reset=1" \
                 -frames:v $((total_samples * 2)) \
                 -f null - 2>&1 | \
                 awk '/crop/ { print $NF }' | \
                 grep "^crop=${original_width}:")  # Only consider crops that maintain original width

    # Analyze all crop heights and their frequencies
    local heights_analysis
    heights_analysis=$(echo "$crop_values" | \
        awk -F':' '{print $2}' | \
        grep -v '^$' | \
        awk -v min=100 '$1 >= min' | \
        sort | uniq -c | sort -nr)

    # Get the most common height
    local most_common_height
    most_common_height=$(echo "$heights_analysis" | head -n1 | awk '{print $2}')

    # Calculate black bar size
    local black_bar_size=$(( (original_height - most_common_height) / 2 ))
    local black_bar_percent=$(( black_bar_size * 100 / original_height ))

    if [ "$black_bar_size" -gt 0 ]; then
        print_check "Found black bars: $(print_stat "${black_bar_size} pixels") ($(print_stat "${black_bar_percent}%") of height)"
    else
        print_check "No significant black bars detected"
    fi

    # Return the crop value if black bars are significant (>1% of height)
    if [ "$black_bar_percent" -gt 1 ]; then
        echo "crop=${original_width}:${most_common_height}:0:${black_bar_size}"
    else
        echo "crop=${original_width}:${original_height}:0:0"
    fi
}

# Set up video encoding options based on input file
setup_video_options() {
    local input_file="$1"
    local disable_crop="$2"
    local video_opts=""

    # Get video width
    local width
    width=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=width -of default=noprint_wrappers=1:nokey=1 "${input_file}")

    # Set quality based on resolution
    local crf
    if [ "$width" -ge 3840 ]; then
        crf=$CRF_UHD
        print_check "UHD quality detected ($(print_stat "${width}px") width), using CRF $(print_stat "$crf")"
    elif [ "$width" -ge 1920 ]; then
        crf=$CRF_HD
        print_check "HD quality detected ($(print_stat "${width}px") width), using CRF $(print_stat "$crf")"
    else
        crf=$CRF_SD
        print_check "SD quality detected ($(print_stat "${width}px") width), using CRF $(print_stat "$crf")"
    fi

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

    if [[ "$IS_DOLBY_VISION" == "true" ]]; then
        video_opts+=" -dolbyvision true"
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