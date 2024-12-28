#!/usr/bin/env bash

###################
# Encoding Functions
###################

source "${SCRIPT_DIR}/encode_formatting.sh"

# Print section header with nice formatting
print_header() {
    local title="$1"
    local width=80
    local padding=$(( (width - ${#title}) / 2 ))
    
    echo
    printf '%*s' "$width" | tr ' ' '='
    echo
    printf "%*s%s%*s\n" "$padding" "" "$title" "$padding" ""
    printf '%*s' "$width" | tr ' ' '='
    echo
    echo
}

# Print section separator
print_separator() {
    echo "----------------------------------------"
}

# Process a single file (perform encoding)
process_file() {
    local input_file="$1"
    local output_file="$2"
    local log_file="$3"
    local filename="$4"

    print_header "Starting Encode"
    
    echo "Input file:  $(print_path "${input_file}")"
    echo "Output file: $(print_path "${output_file}")"
    print_separator
    echo "Processing: $(print_path "${filename}")"

    # Reset global variables
    IS_DOLBY_VISION=false
    HWACCEL_OPTS=""

    # Detect Dolby Vision and set hardware acceleration options
    detect_dolby_vision "${input_file}"

    if [[ "$IS_DOLBY_VISION" == "true" ]]; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            print_warning "Dolby Vision detected, disabling hardware acceleration"
        fi
    else
        # Only check hardware acceleration on macOS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            print_check "Checking hardware acceleration capabilities"
            check_hardware_acceleration
            HWACCEL_OPTS=$(configure_hw_accel_options)
        fi
    fi

    # Setup encoding options
    audio_opts=$(setup_audio_options "${input_file}")
    subtitle_opts=$(setup_subtitle_options "${input_file}")
    video_opts=$(setup_video_options "${input_file}" "${DISABLE_CROP}")

    # Format options for display
    local video_display_opts
    video_display_opts=$(echo "${video_opts}" | sed 's/-c:v/    -c:v/; s/ -/\\\n    -/g')

    local audio_display_opts
    audio_display_opts=$(echo "${audio_opts}" | sed 's/-map/    -map/; s/ -/\\\n    -/g')

    local subtitle_display_opts
    subtitle_display_opts=$(echo "${subtitle_opts}" | sed 's/-c:s/    -c:s/; s/ -/\\\n    -/g')

    # Log the ffmpeg command with proper formatting
    print_header "FFmpeg Command"
    
    cat <<-EOF | tee -a "${log_file}"
${FFMPEG} -hide_banner -loglevel warning ${HWACCEL_OPTS} -i "${input_file}" \\
    -map 0:v:0 \\
${video_display_opts} \\
${audio_display_opts} \\
${subtitle_display_opts} \\
    -stats \\
    -y "${output_file}"
EOF

    print_header "Encoding Progress"
    echo "[1/1] Processing: $(print_path "${filename}")"
    echo

    # Execute the actual ffmpeg command
    "${FFMPEG}" -hide_banner -loglevel warning ${HWACCEL_OPTS} -i "${input_file}" \
        -map 0:v:0 \
        ${video_opts} \
        ${audio_opts} \
        ${subtitle_opts} \
        -stats \
        -y "${output_file}"

    local encode_status=$?

    # If hardware acceleration fails, retry with software decoding
    if [ $encode_status -ne 0 ] && [ -n "${HWACCEL_OPTS}" ]; then
        print_warning "Hardware acceleration failed, falling back to software decoding..."

        "${FFMPEG}" -hide_banner -loglevel warning -i "${input_file}" \
            -map 0:v:0 \
            ${video_opts} \
            ${audio_opts} \
            ${subtitle_opts} \
            -stats \
            -y "${output_file}"

        encode_status=$?
    fi

    # Validate the output
    echo
    print_check "Validating output file..."
    if [ $encode_status -eq 0 ] && validate_output "${output_file}"; then
        print_check "Output validation successful"
        return 0
    else
        print_error "Encoding or validation failed for ${filename}"
        rm -f "${output_file}"  # Remove invalid output
        return 1
    fi
}

# Handle processing of a single input file
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

    # Process the file
    process_file "${input_file}" "${output_file}" "${log_file}" "${filename}" 2>&1 | tee "${log_file}"

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        handle_successful_encode "$filename" "$file_start_time" "$input_file" "$output_file"
    else
        echo "Error encoding ${filename}"
    fi
}

# Handle actions after a successful encode
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

# Print completion message after encoding a file
print_completion_message() {
    local filename="$1"
    local elapsed_time="$2"

    local hours minutes seconds
    hours=$((elapsed_time / 3600))
    minutes=$(( (elapsed_time % 3600) / 60 ))
    seconds=$((elapsed_time % 60))

    print_separator
    echo "Completed: ${filename}"
    printf "Encoding time: %02dh %02dm %02ds\n" "$hours" "$minutes" "$seconds"
    echo "Finished encode at $(date)"
    print_separator
}

# Print the final summary after processing all files
print_final_summary() {
    local total_start_time="$1"
    local total_end_time
    total_end_time=$(date +%s)
    local total_elapsed_time=$((total_end_time - total_start_time))

    local total_hours total_minutes total_seconds
    total_hours=$((total_elapsed_time / 3600))
    total_minutes=$(( (total_elapsed_time % 3600) / 60 ))
    total_seconds=$((total_elapsed_time % 60))

    print_header "Encoding Summary"
    
    for i in "${!encoded_files[@]}"; do
        print_encoding_summary "$i"
    done
    
    print_separator
    printf "Total execution time: %02dh %02dm %02ds\n" "$total_hours" "$total_minutes" "$total_seconds"
}

# Main processing function
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
    IFS=$'\n' read -r -d '' -a files < <(find "${INPUT_DIR}" -type f \( -iname "*.mkv" -o -iname "*.mp4" \) -print0 | xargs -0 -n1 echo)

    if [ ${#files[@]} -eq 0 ]; then
        echo "No video files found in ${INPUT_DIR}"
        exit 1
    fi

    # Process each file
    for input_file in "${files[@]}"; do
        process_single_file "$input_file"
    done

    print_final_summary "$total_start_time"
}

# Process a single video file
process_video() {
    local input_file="$1"
    local output_file="$2"
    
    echo "Processing: $(basename "$input_file")"
    
    # Detect Dolby Vision
    detect_dolby_vision "$input_file"
    
    # Check for hardware acceleration only on macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macOS detected, checking hardware acceleration."
        check_hardware_acceleration
        HWACCEL_OPTS=$(configure_hw_accel_options)
    else
        HWACCEL_OPTS=""
    fi
    
    # Configure audio options
    setup_audio_options "$input_file"
    
    # Configure subtitle options
    setup_subtitle_options "$input_file"
    
    # Configure video options
    VIDEO_OPTS=$(setup_video_options "$input_file")
    
    # Run the encoding
    run_encoding "$input_file" "$output_file"
} 