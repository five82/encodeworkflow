#!/usr/bin/env bash

##############################
# Hardware Acceleration Functions
##############################

# Set up hardware acceleration options if available
setup_hwaccel_options() {
    local hwaccel_opts=""
    local hw_available=false

    echo "Checking hardware acceleration support..." >&2

    if [[ "$OSTYPE" == "darwin"* ]]; then
        if "${FFMPEG}" -hide_banner -hwaccels 2>/dev/null | grep -q "videotoolbox"; then
            hw_available=true
            if [[ "$IS_DOLBY_VISION" == "true" ]]; then
                echo "Hardware acceleration available but skipped (Dolby Vision incompatibility)" >&2
                return 0
            fi
            hwaccel_opts="-hwaccel videotoolbox -hwaccel_output_format nv12"
            echo "Enabled VideoToolbox hardware decoding for macOS" >&2
        fi
    # Uncomment and implement when adding Linux support
    # elif [[ "$OSTYPE" == "linux"* ]]; then
    #     # Hardware acceleration checks for Linux
    #     # Implementation needed
    # fi
    fi

    if [ -z "$hwaccel_opts" ]; then
        if [ "$hw_available" = true ]; then
            if [[ "$IS_DOLBY_VISION" == "true" ]]; then
                echo "Hardware acceleration available but skipped (Dolby Vision incompatibility)" >&2
                return 0
            else
                echo "Hardware acceleration available but not used" >&2
            fi
        else
            echo "No supported hardware acceleration found, using software decoding" >&2
        fi
    fi

    printf "%s" "${hwaccel_opts}"
} 