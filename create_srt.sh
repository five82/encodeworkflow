#!/usr/bin/env bash

# Creates a normalized MP3 of the first audio track for Whisper AI SRT transcription
# using two-pass loudnorm normalization.

# Check if an input path was provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <input_video_file_or_directory>"
    exit 1
fi

input_path="$1"

# Check if input path exists
if [ ! -e "$input_path" ]; then
    echo "Error: Input path '$input_path' not found"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &>/dev/null; then
    echo "Error: jq is required but not installed. Please install jq."
    exit 1
fi

# Function to process a single video file
process_video_file() {
    local input_file="$1"
    local base_name=$(basename "$input_file")
    local output_file="/tmp/${base_name%.*}.mp3"
    local srt_file="${input_file%.*}.srt" # Output SRT in the same directory as input

    echo "--------------------------------------------------"
    echo "Processing file: $input_file"
    echo "--------------------------------------------------"

    # ---------------------------
    # First Pass: Measure Loudness
    # ---------------------------
    echo "Measuring loudness parameters for $base_name..."
    measure_output=$(ffmpeg -hide_banner -loglevel info -threads auto -i "$input_file" -map 0:a:0 \
    -af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null - 2>&1 | sed -n '/{/,/}/p')

    if [ -z "$measure_output" ]; then
        echo "Error: Failed to measure loudness for $base_name."
        return 1 # Continue with next file if in a loop
    fi

    # Parse measured values using jq
    input_i=$(echo "$measure_output" | jq -r '.input_i')
    input_tp=$(echo "$measure_output" | jq -r '.input_tp')
    input_lra=$(echo "$measure_output" | jq -r '.input_lra')
    input_thresh=$(echo "$measure_output" | jq -r '.input_thresh')
    offset=$(echo "$measure_output" | jq -r '.offset')

    # If offset is null, default to 0
    if [ "$offset" = "null" ]; then
        offset=0
    fi

    echo "Measured values for $base_name:"
    echo "  input_i     : $input_i"
    echo "  input_tp    : $input_tp"
    echo "  input_lra   : $input_lra"
    echo "  input_thresh: $input_thresh"
    echo "  offset      : $offset"

    # ----------------------------------------------
    # Second Pass: Apply Normalization and Convert MP3
    # ----------------------------------------------
    echo "Applying loudness normalization and converting to mp3 for $base_name..."
    ffmpeg -hide_banner -loglevel error -threads auto -i "$input_file" -map 0:a:0 \
    -af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=$input_i:measured_TP=$input_tp:measured_LRA=$input_lra:measured_thresh=$input_thresh:offset=$offset:linear=true:print_format=summary" \
    -ac 2 -ar 16000 -c:a libmp3lame -q:a 0 "$output_file"

    if [ $? -ne 0 ]; then
        echo "Error during MP3 conversion for $base_name"
        rm -f "$output_file" # Clean up partial file
        return 1 # Continue with next file if in a loop
    fi
    echo "Successfully converted $base_name to MP3: $output_file"

    # ----------------------------------------------
    # Create SRT Transcription
    # ----------------------------------------------
    echo "Creating srt transcription for $base_name with whisperx..."
    # Output SRT to the same directory as the input video file
    uvx whisperx "$output_file" --model large-v3 --output_format srt --segment_resolution sentence --compute_type float32 --language en --output_dir "$(dirname "$input_file")"

    if [ $? -ne 0 ]; then
        echo "Error during SRT transcription for $base_name"
        rm -f "$output_file" # Clean up MP3 file
        return 1 # Continue with next file if in a loop
    fi

    # Rename the generated SRT file (whisperx might create a file like output.srt)
    # Assuming whisperx outputs to the specified dir with the mp3 name + .srt
    generated_srt_path="$(dirname "$input_file")/$(basename "$output_file" .mp3).srt"
    if [ -f "$generated_srt_path" ]; then
        mv "$generated_srt_path" "$srt_file"
        echo "Successfully created SRT: $srt_file"
    else
        echo "Warning: Could not find generated SRT file at $generated_srt_path to rename."
    fi


    # Clean up temporary MP3 file
    rm -f "$output_file"
    echo "Cleaned up temporary file: $output_file"
    echo "Finished processing: $input_file"
    echo "--------------------------------------------------"
    return 0
}

# Main script logic
if [ -d "$input_path" ]; then
    # Input is a directory
    echo "Input is a directory: $input_path"
    echo "Searching for .mkv files..."
    # Use find to handle filenames with spaces or special characters
    mapfile -d $'\0' mkv_files < <(find "$input_path" -maxdepth 1 -type f -iname "*.mkv" -print0)

    if [ ${#mkv_files[@]} -eq 0 ]; then
        echo "No .mkv files found in the directory: $input_path"
        exit 0
    fi

    echo "Found ${#mkv_files[@]} .mkv files to process:"
    printf "  %s\n" "${mkv_files[@]}"

    processed_count=0
    error_count=0
    for file in "${mkv_files[@]}"; do
        process_video_file "$file"
        if [ $? -eq 0 ]; then
            ((processed_count++))
        else
            ((error_count++))
        fi
    done
    echo "=================================================="
    echo "Batch processing complete."
    echo "Successfully processed: $processed_count files."
    echo "Failed to process: $error_count files."
    echo "=================================================="

elif [ -f "$input_path" ]; then
    # Input is a file
    process_video_file "$input_path"
    if [ $? -ne 0 ]; then
        exit 1 # Exit with error if single file processing failed
    fi
else
    echo "Error: Input path '$input_path' is not a valid file or directory."
    exit 1
fi

exit 0 # Exit successfully
