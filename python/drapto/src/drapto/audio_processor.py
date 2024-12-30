"""Audio processing module for drapto."""

import logging
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio processing tasks like encoding and stream analysis."""

    def __init__(self):
        """Initialize AudioProcessor."""
        pass

    def get_audio_streams(self, input_file: Path) -> List[Dict[str, Any]]:
        """Get audio streams from input file.
        
        Args:
            input_file: Input video file
            
        Returns:
            List of audio stream info dictionaries
        """
        try:
            input_abs = input_file.resolve()
            logger.info(f"Getting audio streams from: {input_abs}")
            
            # Get detailed stream info
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a',
                '-show_entries', 'stream=index,channels,codec_name,bit_rate,channel_layout',
                '-of', 'json',
                str(input_abs)
            ]
            logger.debug(f"FFprobe command: {' '.join(map(str, cmd))}")
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if result.stderr:
                logger.debug(f"FFprobe stderr: {result.stderr}")
            
            data = json.loads(result.stdout)
            logger.info(f"FFprobe output: {json.dumps(data, indent=2)}")
            
            streams = []
            for stream in data.get('streams', []):
                stream_info = {
                    'index': stream.get('index', 0),
                    'channels': stream.get('channels', 2),
                    'codec': stream.get('codec_name', 'unknown'),
                    'bitrate': stream.get('bit_rate', 'unknown'),
                    'layout': stream.get('channel_layout', 'unknown')
                }
                streams.append(stream_info)
                logger.info(f"Found audio stream: {stream_info}")
            
            return streams
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get audio streams: {e}")
            if e.stderr:
                logger.error(f"FFprobe error output: {e.stderr}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse FFprobe output: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to get audio streams: {e}")
            raise

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

    def validate_audio_stream(self, file_path: Path, expected_config: Dict[str, Any]) -> bool:
        """Validate an audio stream matches expected configuration.
        
        Args:
            file_path: Path to audio file
            expected_config: Expected configuration with keys:
                - codec: Expected codec name
                - channels: Expected number of channels
                - bitrate: Expected bitrate in kb/s
                - layout: Expected channel layout
                
        Returns:
            True if valid, False if not
        """
        try:
            logger.info(f"Validating audio stream: {file_path}")
            logger.info(f"Expected config: {expected_config}")
            
            # Get stream info
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'a:0',
                '-show_entries', 'stream=codec_name,channels,channel_layout:format=duration',
                '-of', 'json',
                str(file_path)
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            data = json.loads(result.stdout)
            
            if not data.get('streams'):
                logger.error(f"No audio streams found in {file_path}")
                return False
                
            stream = data['streams'][0]
            logger.info(f"Found stream info: {json.dumps(stream, indent=2)}")
            
            # Check codec
            codec = stream.get('codec_name', 'unknown')
            if codec != expected_config['codec']:
                logger.error(f"Wrong codec: expected {expected_config['codec']}, got {codec}")
                return False
                
            # Check channels
            channels = stream.get('channels', 0)
            if channels != expected_config['channels']:
                logger.error(f"Wrong channel count: expected {expected_config['channels']}, got {channels}")
                return False
                
            # Check layout if available
            if 'channel_layout' in stream:
                layout = stream.get('channel_layout')
                if layout != expected_config['layout']:
                    logger.error(f"Wrong channel layout: expected {expected_config['layout']}, got {layout}")
                    return False
            
            # Calculate actual bitrate from file size and duration
            duration = float(data['format']['duration'])
            file_size = file_path.stat().st_size
            actual_bitrate = int((file_size * 8) / (duration * 1000))  # Convert to kbps
            expected_bitrate = int(expected_config['bitrate'].rstrip('k'))
            
            # Allow 30% variance in bitrate since Opus is VBR
            if abs(actual_bitrate - expected_bitrate) > (expected_bitrate * 0.3):
                logger.error(f"Bitrate outside acceptable range: expected ~{expected_bitrate}k ±30%, got {actual_bitrate}k")
                return False
                    
            logger.info(f"Audio validation passed for {file_path}")
            logger.debug(f"Stream info: {json.dumps(stream, indent=2)}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to validate audio: {e}")
            if e.stderr:
                logger.error(f"FFprobe error output: {e.stderr}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse FFprobe output: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to validate audio: {e}")
            return False

    def encode_audio(self, input_file: Path, output_file: Path) -> bool:
        """Encode all audio streams from input file using libopus.
        
        Uses channel layout filtering to work around a libopus bug where channel
        mappings can be incorrect. The filter forces libopus to use standard
        channel layouts (7.1, 5.1, stereo, mono) which prevents mapping issues.
        
        Args:
            input_file: Input video file
            output_file: Output audio file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            input_abs = input_file.resolve()
            output_abs = output_file.resolve()
            
            # Get audio streams
            streams = self.get_audio_streams(input_abs)
            if not streams:
                logger.warning("No audio streams found")
                return False

            # Create output directory if needed
            output_file.parent.mkdir(parents=True, exist_ok=True)

            # Process each audio track separately
            encoded_tracks = []
            for i, stream in enumerate(streams):
                channels = stream['channels']
                
                # Get bitrate, layout and normalized channel count
                bitrate, layout, norm_channels = self.get_audio_config(channels)
                logger.info(f"Configuring audio stream {i}: {norm_channels} channels, {layout} layout, {bitrate} bitrate")
                logger.info(f"Original stream info: {stream}")
                
                # Encode audio track
                track_output = output_file.parent / f"audio-{i}.mkv"
                track_abs = track_output.resolve()
                
                cmd = [
                    'ffmpeg', '-hide_banner', '-loglevel', 'info',
                    '-i', str(input_abs),
                    '-map', f'0:a:{i}',  # Use audio stream index i, not stream['index']
                    '-c:a', 'libopus',
                    '-af', 'aformat=channel_layouts=7.1|5.1|stereo|mono',
                    '-application', 'audio',
                    '-vbr', 'on',
                    '-compression_level', '10',
                    '-frame_duration', '20',
                    '-b:a', bitrate,
                    '-avoid_negative_ts', 'make_zero',
                    '-f', 'matroska',
                    str(track_abs)
                ]
                
                logger.info(f"FFmpeg command for track {i}: {' '.join(map(str, cmd))}")
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                if result.stderr:
                    logger.info(f"FFmpeg stderr for track {i}: {result.stderr}")
                
                # Validate the encoded track
                expected_config = {
                    'codec': 'opus',
                    'channels': norm_channels,
                    'bitrate': bitrate,
                    'layout': layout
                }
                
                if not self.validate_audio_stream(track_abs, expected_config):
                    logger.error(f"Audio validation failed for track {i}")
                    return False
                    
                encoded_tracks.append(track_abs)
            
            # Mux all audio tracks together
            mux_cmd = [
                'ffmpeg', '-hide_banner', '-loglevel', 'info'
            ]
            
            # Add each audio track
            for track in encoded_tracks:
                mux_cmd.extend(['-i', str(track)])
            
            # Add mapping and output
            for i in range(len(streams)):
                mux_cmd.extend(['-map', f'{i}:a:0'])
            
            mux_cmd.extend([
                '-c', 'copy',  # Just copy streams, no re-encoding
                str(output_abs)
            ])
            
            logger.info(f"FFmpeg muxing command: {' '.join(map(str, mux_cmd))}")
            result = subprocess.run(mux_cmd, check=True, capture_output=True, text=True)
            if result.stderr:
                logger.info(f"FFmpeg muxing stderr: {result.stderr}")
            
            # Validate final output
            for i, stream in enumerate(streams):
                channels = stream['channels']
                bitrate, layout, norm_channels = self.get_audio_config(channels)
                
                expected_config = {
                    'codec': 'opus',
                    'channels': norm_channels,
                    'bitrate': bitrate,
                    'layout': layout
                }
                
                # Use ffprobe to check each stream in the output
                cmd = [
                    'ffprobe', '-v', 'error',
                    '-select_streams', f'a:{i}',
                    '-show_entries', 'stream=codec_name,channels,bit_rate,channel_layout',
                    '-of', 'json',
                    str(output_abs)
                ]
                
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                data = json.loads(result.stdout)
                logger.info(f"Final output stream {i} info: {json.dumps(data, indent=2)}")
                
                if not data.get('streams'):
                    logger.error(f"No audio stream {i} found in final output")
                    return False
                    
                stream_info = data['streams'][0]
                if stream_info.get('codec_name') != 'opus':
                    logger.error(f"Wrong codec in final output stream {i}: expected opus, got {stream_info.get('codec_name')}")
                    return False
            
            # Clean up intermediate files
            for track in encoded_tracks:
                if track.exists():
                    track.unlink()
            
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to encode audio: {e}")
            if e.stderr:
                logger.error(f"FFmpeg error output: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Failed to encode audio: {e}")
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
