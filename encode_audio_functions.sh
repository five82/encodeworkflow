#!/usr/bin/env bash

###################
# Audio Functions
###################

# Set up audio encoding options based on input file
setup_audio_options() {
    local input_file="$1"
    local audio_opts=""
    local stream_index=0

    # Check if there are any audio streams
    local audio_stream_count
    audio_stream_count=$("${FFPROBE}" -v error -select_streams a -show_entries stream=index -of csv=p=0 "${input_file}" | wc -l)

    if [ "$audio_stream_count" -eq 0 ]; then
        echo "No audio streams found" >&2
        return 0
    fi

    # Get audio channels for each stream
    IFS=$'\n' read -r -d '' -a audio_channels < <("${FFPROBE}" -v error -select_streams a -show_entries stream=channels -of csv=p=0 "${input_file}" && printf '\0')
    echo "Detected audio channels: ${audio_channels[@]}" >&2

    for num_channels in "${audio_channels[@]}"; do
        # Skip empty or invalid streams
        if [ -z "$num_channels" ] || [ "$num_channels" -eq 0 ]; then
            echo "Skipping invalid audio stream $stream_index" >&2
            continue
        fi

        # Standardize channel layouts and bitrates
        case $num_channels in
            1)  bitrate="64k"; layout="mono" ;;
            2)  bitrate="128k"; layout="stereo" ;;
            6)  bitrate="256k"; layout="5.1" ;;
            8)  bitrate="384k"; layout="7.1" ;;
            *)  echo "Unsupported channel count ($num_channels) for stream $stream_index, defaulting to stereo" >&2
                num_channels=2
                bitrate="128k"
                layout="stereo"
                ;;
        esac

        # Apply consistent audio encoding settings
        audio_opts+=" -map 0:a:${stream_index}"
        audio_opts+=" -c:a:${stream_index} libopus"
        audio_opts+=" -b:a:${stream_index} ${bitrate}"
        audio_opts+=" -ac:${stream_index} ${num_channels}"

        # Apply consistent channel layout filter to avoid libopus mapping bugs
        audio_opts+=" -filter:a:${stream_index} aformat=channel_layouts=7.1|5.1|stereo|mono"

        # Set consistent opus-specific options
        audio_opts+=" -application:a:${stream_index} audio"
        audio_opts+=" -frame_duration:a:${stream_index} 20"
        audio_opts+=" -vbr:a:${stream_index} on"
        audio_opts+=" -compression_level:a:${stream_index} 10"

        echo "Configured audio stream $stream_index: ${num_channels} channels, ${layout} layout, ${bitrate} bitrate" >&2
        ((stream_index++))
    done

    echo "Final audio options: ${audio_opts}" >&2
    printf "%s" "${audio_opts}"
} 