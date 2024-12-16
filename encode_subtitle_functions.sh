#!/usr/bin/env bash

###################
# Subtitle Functions
###################

# Set up subtitle options based on input file
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