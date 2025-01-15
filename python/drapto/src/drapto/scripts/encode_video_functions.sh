#!/usr/bin/env bash

###################
# Video Functions
###################

source "${SCRIPT_DIR}/utils/formatting.sh"

# Get video encoding options based on input file analysis
get_video_encode_options() {
    local input_file="$1"
    local IS_DOLBY_VISION="$2"
    local crop_filter="$3"
    local crf="$4"

    # Base video encoding options
    local video_opts="-c:v libsvtav1 \
        -preset ${PRESET} \
        -crf ${crf} \
        -svtav1-params tune=0:film-grain=0:film-grain-denoise=0"

    if [[ "$IS_DOLBY_VISION" == "true" ]]; then
        video_opts+=" -dolbyvision true"
    fi

    # Add crop filter if provided
    if [[ -n "$crop_filter" ]]; then
        video_opts+=" -vf $crop_filter"
    fi

    echo "$video_opts"
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
    
    # Get video encoding options
    video_opts=$(get_video_encode_options "${input_file}" "${IS_DOLBY_VISION}" "${crop_filter}" "${crf}")

    printf "%s" "${video_opts}"
}

# Concatenate encoded segments back into a single file
concatenate_segments() {
    local output_file="$1"
    local concat_file="${WORKING_DIR}/concat.txt"

    # Ensure directories exist
    mkdir -p "${WORKING_DIR}" "${ENCODED_SEGMENTS_DIR}"

    # Debug: show contents of encoded segments directory
    echo "Debug: Contents of ${ENCODED_SEGMENTS_DIR}:"
    ls -l "${ENCODED_SEGMENTS_DIR}" || echo "Failed to list directory"

    # Create concat file with proper format
    > "$concat_file"
    
    # Check if there are any mkv files
    if ! compgen -G "${ENCODED_SEGMENTS_DIR}/*.mkv" > /dev/null; then
        error "No .mkv files found in ${ENCODED_SEGMENTS_DIR}"
        return 1
    fi

    for segment in "${ENCODED_SEGMENTS_DIR}"/*.mkv; do
        if [[ -f "$segment" ]]; then
            echo "Debug: Adding segment: $segment"
            echo "file '$(realpath "$segment")'" >> "$concat_file"
        fi
    done

    if [[ ! -s "$concat_file" ]]; then
        error "No segments found to concatenate"
        echo "Debug: concat.txt is empty or missing"
        return 1
    fi

    echo "Debug: Contents of concat.txt:"
    cat "$concat_file"

    # Concatenate video segments directly to output file
    if ! "$FFMPEG" -hide_banner -loglevel error -f concat -safe 0 -i "$concat_file" -c copy "$output_file"; then
        error "Failed to concatenate video segments"
        return 1
    fi
}

# Clean up temporary files
cleanup_temp_files() {
    print_check "Cleaning up temporary files..."
    rm -rf "$SEGMENTS_DIR" "$ENCODED_SEGMENTS_DIR" "$WORKING_DIR"
    mkdir -p "$WORKING_DIR"
}