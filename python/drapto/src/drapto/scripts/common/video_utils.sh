#!/usr/bin/env bash

###################
# Video Functions
###################

source "${SCRIPT_DIR}/utils/formatting.sh"

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
        print_check "Dolby Vision not detected"
        IS_DOLBY_VISION=false
        return 1
    fi
}
