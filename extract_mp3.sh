#!/bin/bash

# Creates an mp3 of the first audio track for Whisper AI SRT transcription

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

# Convert to MP3
ffmpeg -i "$input_file" -map 0:a:0 -c:a libmp3lame -q:a 0 -threads auto "$output_file"

if [ $? -eq 0 ]; then
    echo "Successfully converted to: $output_file"
else
    echo "Error during conversion"
    exit 1
fi