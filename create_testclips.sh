#!/bin/bash

# Default values
CLIP_DURATION=120  # 2 minutes in seconds
NUM_CLIPS=3
SAFETY_MARGIN=0.85  # Use only first 85% of video

# Function to display usage
usage() {
    echo "Usage: $0 -i input_video [-d duration_in_seconds] [-n number_of_clips]"
    echo "Options:"
    echo "  -i: Input video file (required)"
    echo "  -d: Duration of each clip in seconds (default: 120)"
    echo "  -n: Number of clips to generate (default: 3)"
    exit 1
}

# Parse command line arguments
while getopts "i:d:n:h" opt; do
    case $opt in
        i) INPUT_VIDEO="$OPTARG";;
        d) CLIP_DURATION="$OPTARG";;
        n) NUM_CLIPS="$OPTARG";;
        h) usage;;
        ?) usage;;
    esac
done

# Check if input video is provided
if [ -z "$INPUT_VIDEO" ]; then
    echo "Error: Input video is required"
    usage
fi

# Check if input video exists
if [ ! -f "$INPUT_VIDEO" ]; then
    echo "Error: Input video file does not exist"
    exit 1
fi

# Get video duration in seconds using ffprobe
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT_VIDEO")
DURATION=${DURATION%.*}  # Remove decimal places

# Calculate the maximum start time to ensure we don't go into end credits
MAX_START_TIME=$(echo "$DURATION * $SAFETY_MARGIN - $CLIP_DURATION" | bc)
MAX_START_TIME=${MAX_START_TIME%.*}  # Remove decimal places

# Get directory and filename of input video
INPUT_DIR="$(dirname "$INPUT_VIDEO")"
INPUT_FILENAME="$(basename "$INPUT_VIDEO")"
INPUT_NAME="${INPUT_FILENAME%.*}"  # Remove extension

# Create clips subdirectory
CLIPS_DIR="${INPUT_DIR}/clips"
mkdir -p "$CLIPS_DIR"

# Array to store used time ranges
declare -a USED_RANGES=()

# Function to check if a time range overlaps with existing ranges
check_overlap() {
    local new_start=$1
    local new_end=$((new_start + CLIP_DURATION))
    
    for range in "${USED_RANGES[@]}"; do
        local start=${range%-*}
        local end=${range#*-}
        
        # Check if ranges overlap
        if [ $new_start -lt $end ] && [ $new_end -gt $start ]; then
            return 1  # Overlap found
        fi
    done
    return 0  # No overlap
}

# Function to get a valid random timestamp
get_valid_timestamp() {
    local attempts=0
    local max_attempts=100
    
    while [ $attempts -lt $max_attempts ]; do
        local timestamp=$((RANDOM % MAX_START_TIME))
        
        if check_overlap $timestamp; then
            # Add the new range to used ranges
            USED_RANGES+=("$timestamp-$((timestamp + CLIP_DURATION))")
            # Sort ranges for better overlap checking
            IFS=$'\n' USED_RANGES=($(sort -n -t'-' -k1,1 <<<"${USED_RANGES[*]}"))
            echo $timestamp
            return 0
        fi
        
        attempts=$((attempts + 1))
    done
    
    echo "Error: Could not find non-overlapping timestamp after $max_attempts attempts"
    return 1
}

# Generate clips
for ((i=1; i<=$NUM_CLIPS; i++)); do
    # Get non-overlapping random start time
    START_TIME=$(get_valid_timestamp)
    if [ $? -ne 0 ]; then
        echo "$START_TIME"
        exit 1
    fi
    
    # Generate output filename in clips subdirectory
    OUTPUT_FILE="${CLIPS_DIR}/${INPUT_NAME}_clip${i}_${START_TIME}s.${INPUT_FILENAME##*.}"
    
    echo "Generating clip $i of $NUM_CLIPS (starting at ${START_TIME}s)"
    
    # Create clip using ffmpeg with stream copy (no transcoding)
    ffmpeg -ss "$START_TIME" -i "$INPUT_VIDEO" -t "$CLIP_DURATION" \
        -c copy -map 0 -map_chapters -1 -avoid_negative_ts 1 \
        "$OUTPUT_FILE" -y 2>/dev/null
        
    if [ $? -eq 0 ]; then
        echo "Successfully created: \"$OUTPUT_FILE\""
    else
        echo "Error creating clip $i"
    fi
done

echo "Done! Clips have been created in: \"$CLIPS_DIR\""
