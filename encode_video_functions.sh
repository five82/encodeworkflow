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

# Set up video encoding options based on input file
setup_video_options() {
    local input_file="$1"

    # Get video width
    local width
    width=$("${FFPROBE}" -v error -select_streams v:0 -show_entries stream=width -of default=noprint_wrappers=1:nokey=1 "$input_file")

    # Set CRF based on video width
    local crf
    if [ "$width" -le 1280 ]; then  # 720p or lower
        crf=$CRF_SD
        echo "SD quality detected (width: ${width}px), using CRF ${crf}" >&2
    elif [ "$width" -le 1920 ]; then  # 1080p or lower
        crf=$CRF_HD
        echo "HD quality detected (width: ${width}px), using CRF ${crf}" >&2
    else  # 4K and above
        crf=$CRF_UHD
        echo "UHD quality detected (width: ${width}px), using CRF ${crf}" >&2
    fi

    local video_opts="-vf format=${PIX_FMT} \
        -c:v libsvtav1 \
        -preset ${PRESET} \
        -crf ${crf} \
        -svtav1-params ${SVT_PARAMS} "

    if [[ "$IS_DOLBY_VISION" == "true" ]]; then
        video_opts+=" -dolbyvision true"
        echo "Using Dolby Vision encoding settings" >&2
    else
        echo "Using standard encoding settings" >&2
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