#!/usr/bin/env bash

# Creates a normalized MP3 of the first audio track for Whisper AI SRT transcription
# using two-pass loudnorm normalization.

# Check if an input file was provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <input_video_file>"
    exit 1
fi

input_file="$1"
output_file="${input_file%.*}.mp3"

# Check if input file exists
if [ ! -f "$input_file" ]; then
    echo "Error: Input file '$input_file' not found"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &>/dev/null; then
    echo "Error: jq is required but not installed. Please install jq."
    exit 1
fi

# ---------------------------
# First Pass: Measure Loudness
# ---------------------------
echo "Measuring loudness parameters..."
measure_output=$(ffmpeg -hide_banner -loglevel info -threads auto -i "$input_file" -map 0:a:0 \
-af "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json" -f null - 2>&1 | sed -n '/{/,/}/p')

if [ -z "$measure_output" ]; then
    echo "Error: Failed to measure loudness."
    exit 1
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

echo "Measured values:"
echo "  input_i     : $input_i"
echo "  input_tp    : $input_tp"
echo "  input_lra   : $input_lra"
echo "  input_thresh: $input_thresh"
echo "  offset      : $offset"

# ----------------------------------------------
# Second Pass: Apply Normalization and Convert MP3
# ----------------------------------------------
echo "Applying loudness normalization and converting to mp3..."
ffmpeg -hide_banner -loglevel error -threads auto -i "$input_file" -map 0:a:0 \
-af "loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=$input_i:measured_TP=$input_tp:measured_LRA=$input_lra:measured_thresh=$input_thresh:offset=$offset:linear=true:print_format=summary" \
-ac 2 -ar 16000 -c:a libmp3lame -q:a 0 "$output_file"

if [ $? -eq 0 ]; then
    echo "Successfully converted to: $output_file"
else
    echo "Error during conversion"
    exit 1
fi

echo "Creating srt transcription with whisperx"
uvx whisperx "$output_file" --model large-v3 --output_format srt --segment_resolution sentence --compute_type float32 --language en
echo "srt transcription complete"
echo "Cleaning up $output_file"
rm -f "$output_file"
