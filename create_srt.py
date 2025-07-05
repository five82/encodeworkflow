#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "whisperx",
#     "torch",
# ]
# ///
#
# Usage: uv run create_srt.py <input_path>
# Example: uv run create_srt.py video.mkv
# Example: uv run create_srt.py /path/to/video/directory

import os
import sys
import subprocess
import json
import argparse
from pathlib import Path
import whisperx
import torch

def process_video_file(input_file: Path, model, device: str):
    """
    Processes a single video file to generate an SRT transcription file.

    This function performs the following steps:
    1. Extracts the first audio track from the input video file.
    2. Uses a two-pass `ffmpeg` `loudnorm` filter to normalize the audio and encode it as an MP3.
    3. Transcribes the normalized MP3 audio to an SRT file using `whisperx`.
    4. Cleans up the temporary MP3 file.
    """
    base_name = input_file.name
    output_file = Path(f"/tmp/{input_file.stem}.mp3")
    srt_file = input_file.with_suffix(".srt")

    print("--------------------------------------------------")
    print(f"Processing file: {input_file}")
    print("--------------------------------------------------")

    # First Pass: Measure Loudness
    print(f"Measuring loudness parameters for {base_name}...")
    measure_command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "info",
        "-threads",
        "auto",
        "-i",
        str(input_file),
        "-map",
        "0:a:0",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
        "-f",
        "null",
        "-",
    ]
    try:
        measure_output_raw = subprocess.check_output(measure_command, stderr=subprocess.STDOUT, text=True)
        # Extract the JSON part of the output
        json_start = measure_output_raw.find('{')
        json_end = measure_output_raw.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            print(f"Error: Could not find JSON in ffmpeg output for {base_name}.")
            return False
        json_output = measure_output_raw[json_start:json_end]
        loudness_data = json.loads(json_output)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error: Failed to measure loudness for {base_name}. Error: {e}")
        return False

    input_i = loudness_data.get("input_i")
    input_tp = loudness_data.get("input_tp")
    input_lra = loudness_data.get("input_lra")
    input_thresh = loudness_data.get("input_thresh")
    offset = loudness_data.get("target_offset", 0.0)

    print(f"Measured values for {base_name}:")
    print(f"  input_i     : {input_i}")
    print(f"  input_tp    : {input_tp}")
    print(f"  input_lra   : {input_lra}")
    print(f"  input_thresh: {input_thresh}")
    print(f"  offset      : {offset}")

    # Second Pass: Apply Normalization and Convert MP3
    print(f"Applying loudness normalization and converting to mp3 for {base_name}...")
    normalize_command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-threads",
        "auto",
        "-i",
        str(input_file),
        "-map",
        "0:a:0",
        "-af",
        f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={input_i}:measured_TP={input_tp}:measured_LRA={input_lra}:measured_thresh={input_thresh}:offset={offset}:linear=true:print_format=summary",
        "-ac",
        "2",
        "-ar",
        "16000",
        "-c:a",
        "libmp3lame",
        "-q:a",
        "0",
        str(output_file),
    ]
    try:
        subprocess.run(normalize_command, check=True)
        print(f"Successfully converted {base_name} to MP3: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error during MP3 conversion for {base_name}. Error: {e}")
        if output_file.exists():
            output_file.unlink()
        return False

    # Create SRT Transcription
    print(f"Creating srt transcription for {base_name} with whisperx...")
    try:
        audio = whisperx.load_audio(str(output_file))
        result = model.transcribe(audio, batch_size=16)
        
        # Align whisper output
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

        # Write SRT
        writer = whisperx.utils.get_writer("srt", str(input_file.parent))
        writer(result, str(output_file))

        print(f"Successfully created SRT: {srt_file}")

    except Exception as e:
        print(f"Error during SRT transcription for {base_name}. Error: {e}")
        if output_file.exists():
            output_file.unlink()
        return False
    finally:
        # Clean up temporary MP3 file
        if output_file.exists():
            output_file.unlink()
            print(f"Cleaned up temporary file: {output_file}")

    print(f"Finished processing: {input_file}")
    print("--------------------------------------------------")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Generates SRT transcriptions for video files using ffmpeg and whisperx."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Input video file or directory containing .mkv files.",
    )
    args = parser.parse_args()
    input_path = args.input_path

    if not input_path.exists():
        print(f"Error: Input path '{input_path}' not found")
        sys.exit(1)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if torch.cuda.is_available() else "int8"
    
    print(f"Using device: {device} with compute type: {compute_type}")
    model = whisperx.load_model("large-v3", device, compute_type=compute_type)


    if input_path.is_dir():
        print(f"Input is a directory: {input_path}")
        print("Searching for .mkv files...")
        mkv_files = sorted(list(input_path.glob("*.mkv")))

        if not mkv_files:
            print(f"No .mkv files found in the directory: {input_path}")
            sys.exit(0)

        print(f"Found {len(mkv_files)} .mkv files to process:")
        for file in mkv_files:
            print(f"  {file}")

        processed_count = 0
        error_count = 0
        for file in mkv_files:
            if process_video_file(file, model, device):
                processed_count += 1
            else:
                error_count += 1
        
        print("==================================================")
        print("Batch processing complete.")
        print(f"Successfully processed: {processed_count} files.")
        print(f"Failed to process: {error_count} files.")
        print("==================================================")

    elif input_path.is_file():
        if not process_video_file(input_path, model, device):
            sys.exit(1)
    else:
        print(f"Error: Input path '{input_path}' is not a valid file or directory.")
        sys.exit(1)

if __name__ == "__main__":
    main()