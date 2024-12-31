"""Audio processing module for drapto."""

import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

from loguru import logger

class AudioProcessor:
    """Handles audio processing tasks like encoding and stream analysis."""

    def __init__(self, fmt):
        """Initialize AudioProcessor."""
        self.fmt = fmt

    def get_audio_streams(self, input_file: Path) -> List[Dict[str, Any]]:
        """Get audio streams from input file."""
        # Run ffprobe
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-select_streams', 'a',
            str(input_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)
        
        streams = []
        for stream in probe_data.get('streams', []):
            if stream.get('codec_type') == 'audio' or 'codec_type' not in stream:
                stream_info = {
                    'index': stream.get('index', 0),
                    'channels': stream.get('channels', 2),
                    'codec': stream.get('codec_name', 'unknown'),
                    'bitrate': stream.get('bit_rate', 'unknown'),
                    'layout': stream.get('channel_layout', 'stereo')
                }
                streams.append(stream_info)
                logger.debug(f"Found audio stream: {stream_info}")
        
        return streams

    def get_audio_config(self, channels: int) -> Tuple[str, str, int]:
        """Get audio bitrate, layout and channel count based on input channels.
        
        Args:
            channels: Number of audio channels
            
        Returns:
            Tuple of (bitrate, layout, channels)
        """
        if channels == 1:
            return "64k", "mono", 1
        elif channels == 2:
            return "128k", "stereo", 2
        elif channels == 6:
            return "256k", "5.1", 6
        elif channels == 8:
            return "384k", "7.1", 8
        else:
            logger.warning(f"Unsupported channel count ({channels}), defaulting to stereo")
            return "128k", "stereo", 2  # Force to stereo for unsupported counts

    def validate_audio_stream(self, output_file: Path, expected_config: Dict[str, Any]) -> bool:
        """Validate encoded audio stream matches expected configuration."""
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-select_streams', 'a',
            str(output_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(result.stdout)
        
        if not probe_data.get('streams'):
            logger.error("No audio streams found in output file")
            return False
            
        stream = probe_data['streams'][0]
        stream_info = {
            'codec_name': stream.get('codec_name'),
            'channels': stream.get('channels'),
            'channel_layout': stream.get('channel_layout')
        }
        
        # Validate codec
        if stream_info['codec_name'] != expected_config['codec']:
            logger.error(f"Codec mismatch: expected {expected_config['codec']}, got {stream_info['codec_name']}")
            return False
            
        # Validate channels
        if stream_info['channels'] != expected_config['channels']:
            logger.error(f"Channel count mismatch: expected {expected_config['channels']}, got {stream_info['channels']}")
            return False
            
        # Validate layout
        if stream_info['channel_layout'] != expected_config['layout']:
            logger.error(f"Channel layout mismatch: expected {expected_config['layout']}, got {stream_info['channel_layout']}")
            return False
            
        logger.info(f"✓ Audio validation passed: {stream_info['codec_name']}, {stream_info['channels']} channels, {stream_info['channel_layout']} layout")
        return True

    def get_audio_info(self, input_file: Path) -> Dict[str, Any]:
        """Get audio information for status messages.
        
        Args:
            input_file: Input video file
            
        Returns:
            Dictionary with audio info or None if no audio
        """
        try:
            streams = self.get_audio_streams(input_file)
            if not streams:
                return None
                
            # Get first stream info
            stream = streams[0]
            
            # Get bitrate config
            bitrate, layout, channels = self.get_audio_config(stream['channels'])
            bitrate_num = int(bitrate.rstrip('k'))
            
            return {
                'channels': channels,
                'layout': layout,
                'bitrate': bitrate_num
            }
            
        except Exception as e:
            logger.error(f"Failed to get audio info: {e}")
            return None

    def _format_ffmpeg_command(self, cmd: list[str]) -> str:
        """Format FFmpeg command for readable output.
        
        Args:
            cmd: FFmpeg command as list of arguments
            
        Returns:
            Formatted command string
        """
        # Group related arguments together
        formatted_parts = []
        i = 0
        while i < len(cmd):
            if cmd[i].startswith('-'):
                # Collect all values for this flag
                values = []
                i += 1
                while i < len(cmd) and not cmd[i].startswith('-'):
                    values.append(cmd[i])
                    i += 1
                formatted_parts.append(f"{cmd[i-len(values)-1]} {' '.join(values)}")
            else:
                formatted_parts.append(cmd[i])
                i += 1
        
        # Join with newlines and indent
        return "    " + "\n    ".join(formatted_parts)

    def encode_audio(self, input_file: Path, output_file: Path, work_dir: Path) -> bool:
        """Encode audio streams from input file to output file.
        
        Args:
            input_file: Input video file
            output_file: Output audio file
            work_dir: Working directory for intermediate files
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get audio info
            audio_info = self.get_audio_info(input_file)
            if not audio_info:
                logger.error("No audio info found")
                return False
                
            # Ensure output directories exist
            work_dir.mkdir(parents=True, exist_ok=True)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Get audio streams from input
            streams = self.get_audio_streams(input_file)
            if not streams:
                logger.error("No audio streams found in input file")
                return False
                
            # Process each audio stream
            for i, stream in enumerate(streams):
                # Configure stream settings
                channels = stream['channels']
                bitrate, layout, norm_channels = self.get_audio_config(channels)
                
                logger.info(f"✓ Processing audio track {i}: {channels} channels, {layout} layout, {bitrate} bitrate")
                
                # Build intermediate output path
                intermediate_output = work_dir / f"audio-{i}.mkv"
                
                # Build ffmpeg command
                cmd = [
                    'ffmpeg',
                    "-hide_banner",
                    "-loglevel", "warning",
                    "-i", str(input_file),
                    "-map", "0:a:0",
                    "-c:a", "libopus",
                    "-af", "aformat=channel_layouts=7.1|5.1|stereo|mono",
                    "-application", "audio",
                    "-vbr", "on",
                    "-compression_level", "10",
                    "-frame_duration", "20",
                    "-b:a", "384k",
                    "-avoid_negative_ts", "make_zero",
                    "-f", "matroska",
                    "-y",
                    str(intermediate_output)
                ]
                
                # Print command in readable format
                self.fmt.print_check("FFmpeg command for audio encoding:")
                self.fmt.print_check(self._format_ffmpeg_command(cmd))
                
                # Run encoding
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    if not intermediate_output.exists():
                        logger.error("Failed to create output file")
                        return False
                        
                    # Validate encoded audio
                    expected_config = {
                        'codec': 'opus',
                        'channels': norm_channels,
                        'bitrate': bitrate,
                        'layout': layout
                    }
                    if not self.validate_audio_stream(intermediate_output, expected_config):
                        return False
                        
                    # Copy to final output
                    cmd = [
                        'ffmpeg',
                        "-hide_banner",
                        "-loglevel", "warning",
                        "-i", str(intermediate_output),
                        "-map", '0:a:0',
                        "-c", 'copy',
                        str(output_file)
                    ]
                    subprocess.run(cmd, capture_output=True, text=True, check=True)
                    
                except subprocess.CalledProcessError as e:
                    logger.error(f"FFmpeg error: {e.stderr}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Audio encoding failed: {e}")
            return False

    def validate_audio(self, audio_file: Path) -> bool:
        """Validate encoded audio file.
        
        Args:
            audio_file: Audio file to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if file exists and has size
            if not audio_file.exists() or audio_file.stat().st_size == 0:
                logger.error(f"Audio file {audio_file} is missing or empty")
                return False

            # Try to probe the file
            subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    str(audio_file)
                ],
                check=True,
                capture_output=True
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Audio validation failed: {e}")
            return False
