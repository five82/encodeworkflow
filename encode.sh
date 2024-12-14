#!/usr/bin/env bash

###################
# Configuration
###################

if [[ "$OSTYPE" == "darwin"* ]]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
else
    SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
fi

FFMPEG="${SCRIPT_DIR}/ffmpeg"
FFPROBE="${SCRIPT_DIR}/ffprobe"
INPUT_DIR="${SCRIPT_DIR}/videos/input"
OUTPUT_DIR="${SCRIPT_DIR}/videos/output"
LOG_DIR="${SCRIPT_DIR}/videos/logs"

# Encoding settings
PRESET=6
CRF_SD=26  # For videos <= 720p
CRF_HD=27  # For videos > 720p and <= 1080p
CRF_UHD=29 # For videos > 1080p
SVT_PARAMS="tune=0:film-grain=0:film-grain-denoise=0"
PIX_FMT="yuv420p10le"

# Arrays to store encoding information
declare -a encoded_files
declare -a encoding_times
declare -a input_sizes
declare -a output_sizes

# Dolby Vision detection
IS_DOLBY_VISION=false

###################
# Helper Functions
###################

check_dependencies() {
    if [ ! -x "$FFMPEG" ] || [ ! -x "$FFPROBE" ]; then
        echo "Error: ffmpeg or ffprobe not found in script directory"
        echo "Please run build_ffmpeg.sh first"
        return 1
    fi

    for cmd in mediainfo bc; do
        if ! command -v "$cmd" >/dev/null 2>&1; then
            echo "Error: $cmd not found. Please install $cmd first."
            return 1
        fi
    done
    return 0
}

initialize_directories() {
    mkdir -p "${SCRIPT_DIR}/videos" "${INPUT_DIR}" "${OUTPUT_DIR}" "${LOG_DIR}"
}

get_file_size() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        stat -f%z "$1"
    else
        stat -c%s "$1"
    fi
}

get_timestamp() {
    date "+%Y%m%d_%H%M%S"
}

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

setup_audio_options() {
    local input_file="$1"
    local audio_opts=""
    local stream_index=0
    
    # Check if there are any audio streams
    local audio_stream_count
    audio_stream_count=$("${FFPROBE}" -v error -select_streams a -show_entries stream=index -of csv=p=0 "${input_file}" | wc -l)
    
    if [ "$audio_stream_count" -eq 0 ]; then
        echo "No audio streams found" >&2
        return 0
    fi
    
    # Get audio channels for each stream
    IFS=$'\n' read -r -d '' -a audio_channels < <("${FFPROBE}" -v error -select_streams a -show_entries stream=channels -of csv=p=0 "${input_file}" && printf '\0')
    echo "Detected audio channels: ${audio_channels[@]}" >&2

    for num_channels in "${audio_channels[@]}"; do
        # Skip empty or invalid streams
        if [ -z "$num_channels" ] || [ "$num_channels" -eq 0 ]; then
            echo "Skipping invalid audio stream $stream_index" >&2
            continue
        fi
        
        # Standardize channel layouts and bitrates
        case $num_channels in
            1)  
                bitrate="64k"
                layout="mono"
                ;;
            2)  
                bitrate="128k"
                layout="stereo"
                ;;
            6)  
                bitrate="256k"
                layout="5.1"
                ;;
            8)  
                bitrate="384k"
                layout="7.1"
                ;;
            *)  
                echo "Unsupported channel count ($num_channels) for stream $stream_index, defaulting to stereo" >&2
                num_channels=2
                bitrate="128k"
                layout="stereo"
                ;;
        esac
        
        # Apply consistent audio encoding settings
        audio_opts+=" -map 0:a:${stream_index}"
        audio_opts+=" -c:a:${stream_index} libopus"
        audio_opts+=" -b:a:${stream_index} ${bitrate}"
        audio_opts+=" -ac:${stream_index} ${num_channels}"
        
        # Apply consistent channel layout filter to avoid libopus mapping bugs
        audio_opts+=" -filter:a:${stream_index} aformat=channel_layouts=7.1|5.1|stereo|mono"
        
        # Set consistent opus-specific options
        audio_opts+=" -application:a:${stream_index} audio"
        audio_opts+=" -frame_duration:a:${stream_index} 20"
        audio_opts+=" -vbr:a:${stream_index} on"
        audio_opts+=" -compression_level:a:${stream_index} 10"
        
        echo "Configured audio stream $stream_index: ${num_channels} channels, ${layout} layout, ${bitrate} bitrate" >&2
        ((stream_index++))
    done

    echo "Final audio options: ${audio_opts}" >&2
    printf "%s" "${audio_opts}"
}

setup_subtitle_options() {
    local input_file="$1"
    local subtitle_opts=""
    
    local subtitle_count
    subtitle_count=$("${FFPROBE}" -v error -select_streams s -show_entries stream=index -of csv=p=0 "${input_file}" | wc -l)
    
    if [ "$subtitle_count" -gt 0 ]; then
        subtitle_opts="-c:s copy"
        echo "Found $subtitle_count subtitle stream(s), will copy them" >&2
    else
        echo "No subtitle streams found" >&2
    fi
    
    printf "%s" "${subtitle_opts}"
}

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

    local video_opts="-c:v libsvtav1 \
        -preset ${PRESET} \
        -crf ${crf} \
        -svtav1-params ${SVT_PARAMS} \
        -pix_fmt ${PIX_FMT}"

    if [[ "$IS_DOLBY_VISION" == "true" ]]; then
        video_opts+=" -dolbyvision true"
        echo "Using Dolby Vision optimized encoding settings" >&2
    fi
    
    printf "%s" "${video_opts}"
}

format_size() {
    local size=$1
    local scale=0
    local suffix=("B" "KiB" "MiB" "GiB" "TiB")
    
    while [ "$(echo "$size > 1024" | bc -l)" -eq 1 ] && [ $scale -lt 4 ]; do
        size=$(echo "scale=1; $size / 1024" | bc)
        ((scale++))
    done
    
    # Return just the number, not the unit
    echo "$size"
}

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

validate_output() {
    local output_file="$1"
    local error=0

    echo "Validating output file..."
    
    # Check if file exists and has size
    if [ ! -s "$output_file" ]; then
        echo "Error: Output file is empty or doesn't exist"
        return 1
    fi

    # Check video stream
    local video_stream
    video_stream=$("${FFPROBE}" -v error -select_streams v -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$output_file")
    if [ "$video_stream" != "av1" ]; then
        echo "Error: No AV1 video stream found in output"
        error=1
    else
        local duration
        duration=$("${FFPROBE}" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$output_file")
        echo "Video stream: AV1, Duration: ${duration}s"
    fi

    # Check audio streams
    local audio_count
    audio_count=$("${FFPROBE}" -v error -select_streams a -show_entries stream=codec_name -of default=noprint_wrappers=1:nokey=1 "$output_file" | grep -c "opus" || true)
    if [ "$audio_count" -eq 0 ]; then
        echo "Error: No Opus audio streams found in output"
        error=1
    else
        echo "Audio streams: $audio_count Opus stream(s)"
    fi

    # Compare input and output duration
    local input_duration output_duration
    input_duration=$("${FFPROBE}" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${input_file}")
    output_duration=$("${FFPROBE}" -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$output_file")
    
    # Allow 1 second difference
    local duration_diff
    duration_diff=$(awk "BEGIN {print sqrt(($input_duration - $output_duration)^2)}")
    if (( $(echo "$duration_diff > 1" | bc -l) )); then
        echo "Error: Output duration ($output_duration) differs significantly from input ($input_duration)"
        error=1
    fi

    if [ $error -eq 0 ]; then
        echo "Output validation successful"
        return 0
    else
        echo "Output validation failed"
        return 1
    fi
}

process_file() {
    local input_file="$1"
    local output_file="$2"
    local log_file="$3"
    local filename="$4"

    echo "Starting encode at $(date)"
    echo "Input file: ${input_file}"
    echo "Output file: ${output_file}"
    echo "----------------------------------------"
    echo "Processing: ${filename}"

    detect_dolby_vision "${input_file}"
    
    # Setup encoding options
    audio_opts=$(setup_audio_options "${input_file}")
    subtitle_opts=$(setup_subtitle_options "${input_file}")
    video_opts=$(setup_video_options "${input_file}")
    
    # Prepare video options for display
    video_display_opts="-c:v libsvtav1 \\
    -preset ${PRESET} \\
    -crf ${crf} \\
    -svtav1-params ${SVT_PARAMS} \\
    -pix_fmt ${PIX_FMT}"
    
    if [[ "$IS_DOLBY_VISION" == "true" ]]; then
        video_display_opts+=" \\
    -dolbyvision true"
    fi
    
    cat <<-EOF | tee -a "${log_file}"
Running ffmpeg command:
${FFMPEG} -hide_banner -loglevel warning -i "${input_file}" \\
    -map 0:v:0 \\
${video_display_opts} \\
$(echo "${audio_opts}" | sed 's/ -/\\\n    -/g') \\
$(echo "${subtitle_opts}" | sed 's/ -/\\\n    -/g') \\
    -stats \\
    -y "${output_file}"
EOF
    
    "${FFMPEG}" -hide_banner -loglevel warning -i "${input_file}" \
        -map 0:v:0 \
        ${video_opts} \
        ${audio_opts} \
        ${subtitle_opts} \
        -stats \
        -y "${output_file}"

    # Validate the output
    if ! validate_output "${output_file}"; then
        echo "Error: Output validation failed for ${filename}"
        rm -f "${output_file}"  # Remove invalid output
        return 1
    fi

    return 0
}

###################
# Main Processing
###################

main() {
    if ! check_dependencies; then
        exit 1
    fi

    initialize_directories

    # Start total timing
    local total_start_time
    total_start_time=$(date +%s)

    # Get input files
    local files
    IFS=$'\n' read -r -d '' -a files < <(find "${INPUT_DIR}" -type f -iname "*.mkv" -print0 | tr '\0' '\n')

    if [ ${#files[@]} -eq 0 ]; then
        echo "No MKV files found in ${INPUT_DIR}"
        exit 1
    fi

    # Process each file
    for input_file in "${files[@]}"; do
        process_single_file "$input_file"
    done

    print_final_summary "$total_start_time"
}

process_single_file() {
    local input_file="$1"
    local filename
    filename=$(basename "${input_file}")
    local filename_noext="${filename%.*}"
    local output_file="${OUTPUT_DIR}/${filename}"
    local timestamp
    timestamp=$(get_timestamp)
    local log_file="${LOG_DIR}/${filename_noext}_${timestamp}.log"
    
    local file_start_time
    file_start_time=$(date +%s)
    
    process_file "${input_file}" "${output_file}" "${log_file}" "${filename}" 2>&1 | tee "${log_file}"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        handle_successful_encode "$filename" "$file_start_time" "$input_file" "$output_file"
    else
        echo "Error encoding ${filename}"
    fi
}

handle_successful_encode() {
    local filename="$1"
    local file_start_time="$2"
    local input_file="$3"
    local output_file="$4"

    local file_end_time
    file_end_time=$(date +%s)
    local file_elapsed_time=$((file_end_time - file_start_time))
    
    # Store encoding information
    encoded_files+=("$filename")
    encoding_times+=("$file_elapsed_time")
    input_sizes+=("$(get_file_size "${input_file}")")
    output_sizes+=("$(get_file_size "${output_file}")")
    
    print_completion_message "$filename" "$file_elapsed_time"
}

print_completion_message() {
    local filename="$1"
    local elapsed_time="$2"
    
    local hours minutes seconds
    hours=$(awk "BEGIN {printf \"%.0f\", $elapsed_time/3600}")
    minutes=$(awk "BEGIN {printf \"%.0f\", ($elapsed_time%3600)/60}")
    seconds=$(awk "BEGIN {printf \"%.0f\", $elapsed_time%60}")
    
    echo "----------------------------------------"
    echo "Completed: ${filename}"
    echo "Encoding time: ${hours}h ${minutes}m ${seconds}s"
    echo "Finished encode at $(date)"
    echo "----------------------------------------"
}

print_final_summary() {
    local total_start_time="$1"
    local total_end_time
    total_end_time=$(date +%s)
    local total_elapsed_time=$((total_end_time - total_start_time))
    
    local total_hours total_minutes total_seconds
    total_hours=$(awk "BEGIN {printf \"%.0f\", $total_elapsed_time/3600}")
    total_minutes=$(awk "BEGIN {printf \"%.0f\", ($total_elapsed_time%3600)/60}")
    total_seconds=$(awk "BEGIN {printf \"%.0f\", $total_elapsed_time%60}")

    echo "All files processed successfully!"
    echo "----------------------------------------"
    echo "Encoding Summary:"
    echo "----------------------------------------"
    for i in "${!encoded_files[@]}"; do
        print_encoding_summary "$i"
    done
    echo "Total execution time: ${total_hours}h ${total_minutes}m ${total_seconds}s"

    echo "Using ffmpeg binary: ${FFMPEG}"
    echo "Using ffprobe binary: ${FFPROBE}"
    "${FFMPEG}" -version | head -n 1
}

# Execute main function
main
