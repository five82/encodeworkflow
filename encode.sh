#!/usr/bin/env bash

# Encodes videos with ffmpeg and svt-av1-psy
#
# Required tools:
# - ffmpeg (from build_ffmpeg.sh)
# - ffprobe (from build_ffmpeg.sh)  
# - mediainfo

###################
# Configuration
###################

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
FFMPEG="${SCRIPT_DIR}/ffmpeg"
FFPROBE="${SCRIPT_DIR}/ffprobe"
INPUT_DIR="${SCRIPT_DIR}/videos/input"
OUTPUT_DIR="${SCRIPT_DIR}/videos/output"
LOG_DIR="${SCRIPT_DIR}/videos/logs"

# Encoding settings
PRESET=8
CRF=29
SVT_PARAMS="tune=3:film-grain=0:film-grain-denoise=0:adaptive-film-grain=0"
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
        
        case $num_channels in
            1)  
                bitrate=64k
                layout="mono"
                ;;
            2)  
                bitrate=128k
                layout="stereo"
                ;;
            6)  
                bitrate=256k
                layout="5.1"
                ;;
            8)  
                bitrate=384k
                layout="7.1"
                ;;
            *)  
                if [ "$num_channels" -gt 0 ]; then
                    bitrate="${num_channels}k"
                    layout="$num_channels channels"
                else
                    echo "Invalid channel count for stream $stream_index, skipping" >&2
                    continue
                fi
                ;;
        esac
        
        # Add channel remapping for 5.1
        if [ "$num_channels" -eq 6 ]; then
            audio_opts+=" -map 0:a:${stream_index} -c:a:${stream_index} libopus -filter:a:${stream_index} aformat=channel_layouts=5.1 -b:a:${stream_index} ${bitrate}"
        else
            audio_opts+=" -map 0:a:${stream_index} -c:a:${stream_index} libopus -ac:${stream_index} ${num_channels} -channel_layout:${stream_index} ${layout} -b:a:${stream_index} ${bitrate}"
        fi
        echo "Added bitrate for audio stream $stream_index ($num_channels channels): ${bitrate}" >&2
        ((stream_index++))
    done

    if [ -z "$audio_opts" ]; then
        echo "Warning: No valid audio streams to encode" >&2
        return 0
    fi

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
    local video_opts="-c:v libsvtav1 \
        -preset ${PRESET} \
        -crf ${CRF} \
        -svtav1-params ${SVT_PARAMS} \
        -pix_fmt ${PIX_FMT}"

    if [[ "$IS_DOLBY_VISION" == "true" ]]; then
        video_opts+=" -dolbyvision true"
        echo "Using Dolby Vision optimized encoding settings" >&2
    else
        echo "Using standard encoding settings" >&2
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
    
    printf "%s %s" "$size" "${suffix[$scale]}"
}

print_encoding_summary() {
    local i="$1"
    local time_seconds=${encoding_times[$i]}
    local h=$((time_seconds / 3600))
    local m=$(( (time_seconds % 3600) / 60 ))
    local s=$((time_seconds % 60))
    
    # Use format_size instead of numfmt
    local input_size=$(format_size "${input_sizes[$i]}")
    local output_size=$(format_size "${output_sizes[$i]}")
    
    # Calculate reduction using bc for floating point arithmetic
    local reduction
    reduction=$(echo "scale=1; 100 - (${output_sizes[$i]} * 100 / ${input_sizes[$i]})" | bc)
    
    echo "${encoded_files[$i]}"
    echo "  Encode time: ${h}h ${m}m ${s}s"
    echo "  Input size:  ${input_size}"
    echo "  Output size: ${output_size}"
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

###################
# Initialization
###################

# Check required tools
if [ ! -x "$FFMPEG" ] || [ ! -x "$FFPROBE" ]; then
    echo "Error: ffmpeg or ffprobe not found in script directory"
    echo "Please run build_ffmpeg.sh first"
    exit 1
fi

if ! command -v mediainfo >/dev/null 2>&1; then
    echo "Error: mediainfo not found. Please install mediainfo first."
    echo "On Ubuntu/Debian: sudo apt-get install mediainfo"
    echo "On macOS: brew install mediainfo"
    exit 1
fi

# Create required directories
mkdir -p "${SCRIPT_DIR}/videos" "${INPUT_DIR}" "${OUTPUT_DIR}" "${LOG_DIR}"

###################
# Main Processing
###################

# Start total timing
total_start_time=$(date +%s)

# Get input files
IFS=$'\n' read -r -d '' -a files < <(find "${INPUT_DIR}" -type f -iname "*.mkv" -print0 | tr '\0' '\n')

# Process each file
for input_file in "${files[@]}"; do
    filename=$(basename "${input_file}")
    filename_noext="${filename%.*}"
    output_file="${OUTPUT_DIR}/${filename}"
    timestamp=$(get_timestamp)
    log_file="${LOG_DIR}/${filename_noext}_${timestamp}.log"
    
    file_start_time=$(date +%s)
    
    {
        echo "Starting encode at $(date)"
        echo "Input file: ${input_file}"
        echo "Output file: ${output_file}"
        echo "----------------------------------------"
        echo "Processing: ${filename}"

        detect_dolby_vision "${input_file}"
        
        # Setup encoding options
        audio_opts=$(setup_audio_options "${input_file}")
        subtitle_opts=$(setup_subtitle_options "${input_file}")
        video_opts=$(setup_video_options)
        
        echo "Starting ffmpeg encode..."
        
        # Add before the ffmpeg command
        echo "Video stream details:"
        "${FFPROBE}" -v error -select_streams v -show_entries \
            stream=index,codec_name,width,height,r_frame_rate,pix_fmt \
            -of json "${input_file}"
        
        echo "Audio stream details:"
        "${FFPROBE}" -v error -select_streams a -show_entries \
            stream=index,codec_name,channels,channel_layout,sample_rate,bit_rate \
            -of json "${input_file}"
        
        # Main encoding command
        "${FFMPEG}" -v verbose -i "${input_file}" \
            -map 0:v:0 \
            ${video_opts} \
            ${audio_opts} \
            ${subtitle_opts} \
            -y "${output_file}"

        # Validate the output
        if ! validate_output "${output_file}"; then
            echo "Error: Output validation failed for ${filename}"
            rm -f "${output_file}"  # Remove invalid output
            exit 1
        fi
          
    } 2>&1 | tee "${log_file}"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        file_end_time=$(date +%s)
        file_elapsed_time=$((file_end_time - file_start_time))
        
        # Store encoding information
        encoded_files+=("$filename")
        encoding_times+=("$file_elapsed_time")
        input_sizes+=("$(get_file_size "${input_file}")")
        output_sizes+=("$(get_file_size "${output_file}")")
        
        # Print completion message
        hours=$((file_elapsed_time / 3600))
        minutes=$(( (file_elapsed_time % 3600) / 60 ))
        seconds=$((file_elapsed_time % 60))
        
        echo "----------------------------------------"
        echo "Completed: ${filename}"
        echo "Encoding time: ${hours}h ${minutes}m ${seconds}s"
        echo "Finished encode at $(date)"
    else
        echo "Error encoding ${filename}"
    fi
    
    echo "----------------------------------------"
done

###################
# Final Summary
###################

if [ ${#encoded_files[@]} -eq 0 ]; then
    echo "No MKV files found in ${INPUT_DIR}"
    exit 1
fi

# Calculate total time
total_end_time=$(date +%s)
total_elapsed_time=$((total_end_time - total_start_time))
total_hours=$((total_elapsed_time / 3600))
total_minutes=$(( (total_elapsed_time % 3600) / 60 ))
total_seconds=$((total_elapsed_time % 60))

# Print summary
echo "All files processed successfully!"
echo "----------------------------------------"
echo "Encoding Summary:"
echo "----------------------------------------"
for i in "${!encoded_files[@]}"; do
    print_encoding_summary "$i"
done
echo "Total execution time: ${total_hours}h ${total_minutes}m ${total_seconds}s"
