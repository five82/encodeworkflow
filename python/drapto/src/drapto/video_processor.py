"""Main video processing module."""

import os
import platform
import subprocess
import tempfile
import shutil
import logging
import signal
import atexit
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Set
import time
import json

from loguru import logger

from .encoder import VideoEncoder
from .segment_handler import SegmentHandler
from .formatting import TerminalFormatter
from .audio_processor import AudioProcessor
from .work_manager import WorkDirectoryManager

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Main video processing class."""
    
    def __init__(self, config: 'EncodingConfig'):
        """Initialize video processor.
        
        Args:
            config: Encoding configuration
        """
        self.config = config
        self.encoder = VideoEncoder(config)
        self.segment_handler = SegmentHandler(config)
        self.fmt = TerminalFormatter()
        self.audio_processor = AudioProcessor(self.fmt)
        self.stream_sizes: Dict[str, int] = {}
        self.work_manager = WorkDirectoryManager(config)
        
        # Validate configuration
        if config.vmaf_sample_count < 1:
            raise ValueError("VMAF sample count must be at least 1")
        if config.vmaf_sample_length < 1:
            raise ValueError("VMAF sample length must be at least 1 second")
        
    def process_video(self, input_file: Path, output_file: Path) -> None:
        """Process a video file.
        
        Args:
            input_file: Input video file
            output_file: Output video file
        """
        start_time = time.time()
        
        # Print starting info
        self.fmt.print_encode_start(str(input_file), str(output_file))
        
        # Detect Dolby Vision
        is_dolby_vision = self.detect_dolby_vision(input_file)
        self.fmt.print_dolby_check(is_dolby_vision)
        
        if is_dolby_vision:
            # Use FFmpeg directly for Dolby Vision content
            logger.info("Encoding Dolby Vision content using FFmpeg and libsvtav1")
            self.encode_dolby_vision(input_file, output_file)
            return
            
        # For non-Dolby Vision content, proceed with chunked encoding
        with self.work_manager.work_space(output_file) as work_dirs:
            try:
                # Set up file paths
                audio_file = work_dirs['audio'] / "audio.opus"
                video_file = work_dirs['root'] / "video.mkv"
                
                # Encode audio first
                audio_info = self.audio_processor.get_audio_info(input_file)
                if audio_info:
                    self.fmt.print_audio_status(
                        0,  # track number
                        audio_info['channels'],
                        audio_info['layout'],
                        audio_info['bitrate']
                    )
                
                if not self.audio_processor.encode_audio(input_file, audio_file, work_dirs['audio']):
                    logger.error("Failed to encode audio")
                    raise RuntimeError("Audio encoding failed")
                
                # Validate audio
                if not self.audio_processor.validate_audio(audio_file):
                    logger.error("Audio validation failed")
                    raise RuntimeError("Audio validation failed")

                # Get crop filter
                if not self.config.disable_crop:
                    self.fmt.print_black_bar_analysis(24)  # Standard frame count
                    crop_filter = self.detect_crop(input_file)
                    if crop_filter:
                        crop_pixels = int(crop_filter.split('=')[1].split(':')[1])
                        self.fmt.print_black_bar_analysis(24, crop_pixels)
                else:
                    crop_filter = None
                
                # Segment video
                self.fmt.print_check("Cleaning up temporary files...")
                self.segment_handler.segment_video(input_file, work_dirs['segments'])
                
                # Count segments
                segment_count = len(list(work_dirs['segments'].glob('*.mkv')))
                self.fmt.print_segment_status(segment_count)
                
                # Encode segments
                self._encode_segments(work_dirs['segments'], work_dirs['encoded'], crop_filter)
                
                # Validate encoded segments
                self.segment_handler.validate_segments(work_dirs['encoded'])
                
                # Concatenate video segments
                self.segment_handler.concatenate_segments(work_dirs['encoded'], video_file)
                
                # Mux final output
                logger.info("Muxing tracks...")
                mux_cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel", "info",
                    "-i", str(video_file),
                    "-i", str(audio_file),
                    "-i", str(input_file),  # Original file for subtitles/attachments
                    "-map", "0:v:0",  # Video from encoded file
                    "-map", "1:a?",   # Audio from encoded file
                    "-map", "2:s?",   # Subtitles from original
                    "-map", "2:t?",   # Attachments from original
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-c:s", "copy",
                    "-c:t", "copy",
                    str(output_file)
                ]
                logger.info("\nFFmpeg command for muxing tracks:")
                logger.info("\n" + self._format_ffmpeg_command(mux_cmd))
                subprocess.run(mux_cmd, check=True)
                self.fmt.print_check("Successfully muxed all tracks")
                self.fmt.print_check("Cleaning up temporary files...")
                
                # Print encoding summary
                encode_time = time.time() - start_time
                hours = int(encode_time // 3600)
                minutes = int((encode_time % 3600) // 60)
                seconds = int(encode_time % 60)
                time_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
                
                input_size = input_file.stat().st_size
                output_size = output_file.stat().st_size
                
                self.fmt.print_encode_summary(
                    input_size,
                    output_size,
                    time_str,
                    input_file.name
                )
                
            except Exception as e:
                logger.error(f"Error processing video: {e}")
                raise

    def _encode_segments(self, segments_dir: Path, encoded_dir: Path, crop_filter: Optional[str] = None) -> None:
        """Encode video segments.
        
        Args:
            segments_dir: Directory containing input segments
            encoded_dir: Directory for encoded segments
            crop_filter: Optional crop filter string
        """
        encoded_dir.mkdir(parents=True, exist_ok=True)
        
        # Get list of segments
        segments = sorted(segments_dir.glob('*.mkv'))
        total_segments = len(segments)
        
        for i, segment in enumerate(segments, 1):
            output_segment = encoded_dir / segment.name
            
            # Encode the segment
            self.encoder.encode_segment(segment, output_segment, crop_filter)
            
            # Update progress
            encoded_size = sum(f.stat().st_size for f in encoded_dir.glob('*.mkv'))
            progress = (i / total_segments) * 100
            self.fmt.print_encode_progress(progress, self.fmt.format_size(encoded_size))
            
    def process_directory(self, input_dir: Path, output_dir: Path) -> bool:
        """Process all video files in a directory.
        
        Args:
            input_dir: Input directory containing video files
            output_dir: Output directory for processed videos
            
        Returns:
            True if all videos were processed successfully
        """
        self.fmt.print_check(f"Processing directory: {input_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all video files
        video_extensions = ['.mp4', '.mkv', '.mov', '.avi', '.wmv']
        video_files = []
        for f in input_dir.glob('**/*'):
            if (f.is_file() and 
                f.suffix.lower() in video_extensions and 
                not f.name.startswith('._')):
                video_files.append(f)
        
        if not video_files:
            self.fmt.print_error("No video files found")
            return False
            
        self.fmt.print_check(f"Found {len(video_files)} video files")
        
        # Track file stats for final summary
        file_stats = []
        start_time = time.time()
        
        # Process each video
        for video_file in video_files:
            file_start_time = time.time()
            rel_path = video_file.relative_to(input_dir)
            output_file = output_dir / rel_path.with_suffix('.mkv')
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                self.process_video(video_file, output_file)
                
                # Calculate encode time
                encode_time = time.time() - file_start_time
                hours = int(encode_time // 3600)
                minutes = int((encode_time % 3600) // 60)
                seconds = int(encode_time % 60)
                time_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
                
                # Add stats to list
                file_stats.append((
                    video_file.name,
                    video_file.stat().st_size,
                    output_file.stat().st_size,
                    time_str
                ))
                
            except Exception as e:
                logger.error(f"Failed to process {video_file}: {e}")
                return False
                
        # Print final summary
        self.fmt.print_final_summary(file_stats)
        
        return True

    def detect_crop(self, input_file: Path) -> Optional[str]:
        """Detect black bars and return crop filter.
        
        Args:
            input_file: Input video file
            
        Returns:
            Crop filter string if black bars detected, None otherwise
        """
        try:
            logger.info("Analyzing video for black bars...")
            
            # Get original dimensions
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height',
                    '-of', 'json',
                    str(input_file)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            if not data.get('streams'):
                return None
                
            original_width = data['streams'][0].get('width')
            original_height = data['streams'][0].get('height')
            if not original_width or not original_height:
                return None
            
            # Check if input is HDR and get color properties
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=color_transfer,color_primaries,color_space',
                    '-of', 'json',
                    str(input_file)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse JSON output
            data = json.loads(result.stdout)
            stream = data.get('streams', [{}])[0]
            
            # Set initial crop threshold
            crop_threshold = 16
            is_hdr = False
            
            # Check for various HDR formats
            hdr_formats = [
                'smpte2084', 'arib-std-b67', 'smpte428',
                'bt2020-10', 'bt2020-12', 'arib-std-b67',
                'smpte2084'
            ]
            
            if (
                stream.get('color_transfer') in hdr_formats or
                stream.get('color_primaries') in hdr_formats or
                stream.get('color_space') in hdr_formats
            ):
                is_hdr = True
                crop_threshold = 24
                
            # Run crop detection
            result = subprocess.run(
                [
                    'ffmpeg',
                    '-i', str(input_file),
                    '-vf', f'cropdetect=round=2:reset=1:limit={crop_threshold}',
                    '-f', 'null',
                    '-t', '300',  # Sample first 5 minutes
                    '-'
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse crop values
            crop_values = []
            for line in result.stderr.split('\n'):
                if 'crop=' in line:
                    crop = line.split('crop=')[1].split(' ')[0]
                    # Only consider crops that maintain original width
                    if crop.startswith(f'crop={original_width}:'):
                        crop_values.append(crop)
                        
            if not crop_values:
                logger.info("No black bars detected")
                return None
                
            # Use most common crop value
            crop_filter = max(set(crop_values), key=crop_values.count)
            logger.info(f"Detected crop filter: {crop_filter}")
            return crop_filter
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Error detecting crop: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing ffprobe output: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in crop detection: {e}")
            return None

    def detect_dolby_vision(self, input_file: Path) -> bool:
        """Detect if file contains Dolby Vision.
        
        Args:
            input_file: Input video file
            
        Returns:
            True if Dolby Vision is detected
        """
        try:
            # Run ffprobe to get stream info
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-select_streams', 'v',
                str(input_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            probe_data = json.loads(result.stdout)
            
            # Check for Dolby Vision metadata
            for stream in probe_data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    side_data = stream.get('side_data_list', [])
                    for data in side_data:
                        if data.get('side_data_type') == 'DOVI configuration record':
                            logger.info("Dolby Vision detected")
                            return True
                            
            logger.info("Dolby Vision not detected")
            return False
            
        except Exception as e:
            logger.error(f"Error detecting Dolby Vision: {e}")
            return False

    def _configure_hw_accel(self) -> List[str]:
        """Configure hardware acceleration options.
        
        Returns:
            List of FFmpeg hardware acceleration options
        """
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Only support VideoToolbox on Apple Silicon
        if system == 'darwin' and machine in ['arm64', 'aarch64']:
            self.fmt.print_check("Using VideoToolbox hardware acceleration")
            return ['-hwaccel', 'videotoolbox']
            
        self.fmt.print_warning("No hardware acceleration available")
        return []
            
    def _get_audio_track_count(self, input_file: Path) -> int:
        """Get number of audio tracks in file.
        
        Args:
            input_file: Input video file
            
        Returns:
            Number of audio tracks
        """
        try:
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'a',
                    '-show_entries', 'stream=index',
                    '-of', 'csv=p=0',
                    str(input_file)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            count = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            self.fmt.print_check(f"Found {count} audio tracks")
            return count
            
        except subprocess.CalledProcessError as e:
            self.fmt.print_error(f"Error getting audio track count: {str(e)}")
            return 0
            
    def _validate_encoded_segments(self, segments_dir: Path, encoded_dir: Path) -> None:
        """Validate encoded segments.
        
        Args:
            segments_dir: Directory containing original segments
            encoded_dir: Directory containing encoded segments
            
        Raises:
            RuntimeError: If any segments are invalid
        """
        logger.info("Validating encoded segments...")
        
        invalid_segments = []
        for segment in segments_dir.glob("*.mkv"):
            encoded_segment = encoded_dir / segment.name
            
            # Check if encoded segment exists
            if not encoded_segment.exists():
                logger.error(f"Encoded segment does not exist: {encoded_segment}")
                invalid_segments.append(segment.name)
                continue
                
            # Check if encoded segment has minimum size
            if encoded_segment.stat().st_size < 1024:  # 1KB
                logger.error(f"Encoded segment too small: {encoded_segment}")
                invalid_segments.append(segment.name)
                continue
                
            # Check if encoded segment is valid video
            try:
                subprocess.run(["ffprobe", "-v", "error", str(encoded_segment)], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Encoded segment invalid: {encoded_segment}\n{e.stderr}")
                invalid_segments.append(segment.name)
                continue
                
        if invalid_segments:
            raise RuntimeError(f"Found {len(invalid_segments)} invalid segments")
        
        logger.info(f"Successfully validated {len(list(segments_dir.glob('*.mkv')))} segments")

    def _encode_segments(self, segments_dir: Path, encoded_dir: Path, crop_filter: str | None = None) -> None:
        """Encode video segments in parallel.
        
        Args:
            segments_dir: Directory containing segments
            encoded_dir: Directory to store encoded segments
            crop_filter: Optional crop filter
        """
        logger.info("Encoding segments...")
        encoded_dir.mkdir(parents=True, exist_ok=True)
        
        # Create temporary files for commands and bash function
        cmd_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        bash_script = tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False)
        
        try:
            # Write bash wrapper function
            bash_script.write("""#!/bin/bash
set -euo pipefail

# Helper functions
print_check() { echo "✓ $*" >&2; }
error() { echo "✗ $*" >&2; }

encode_single_segment() {
    local segment="$1"
    local output_segment="$2"
    local target_vmaf="$3"
    local crop_filter="$4"
    
    # Skip if already encoded
    if [[ -f "$output_segment" ]] && [[ -s "$output_segment" ]]; then
        print_check "Segment already encoded: $(basename "$segment")"
        return 0
    fi
    
    # Build base command
    local cmd=(
        ab-av1 auto-encode
        --input "$segment"
        --output "$output_segment"
        --encoder libsvtav1
        --min-vmaf "$target_vmaf"
        --preset "${PRESET}"
        --svt "tune=0:film-grain=0:film-grain-denoise=0"
        --keyint 10s
        --samples "${VMAF_SAMPLE_COUNT}"
        --sample-duration "${VMAF_SAMPLE_LENGTH}s"
        --vmaf "n_subsample=8:pool=harmonic_mean"
        --quiet
    )
    
    # Add crop filter if provided
    if [[ -n "$crop_filter" ]]; then
        cmd+=(--vfilter "crop=$crop_filter")
    fi
    
    # Print command
    echo "Running command: ${cmd[*]}" >&2
    
    # First attempt with default settings
    if "${cmd[@]}"; then
        print_check "Successfully encoded segment: $(basename "$segment")"
        return 0
    fi
    
    # Second attempt with more samples
    cmd=(
        ab-av1 auto-encode
        --input "$segment"
        --output "$output_segment"
        --encoder libsvtav1
        --min-vmaf "$target_vmaf"
        --preset "${PRESET}"
        --svt "tune=0:film-grain=0:film-grain-denoise=0"
        --keyint 10s
        --samples "${VMAF_SAMPLE_COUNT}"
        --sample-duration "${VMAF_SAMPLE_LENGTH}s"
        --vmaf "n_subsample=8:pool=harmonic_mean"
        --quiet
    )
    
    if [[ -n "$crop_filter" ]]; then
        cmd+=(--vfilter "crop=$crop_filter")
    fi
    
    echo "Retrying with more samples: ${cmd[*]}" >&2
    
    if "${cmd[@]}"; then
        print_check "Successfully encoded segment with more samples: $(basename "$segment")"
        return 0
    fi
    
    # Final attempt with lower VMAF target
    local lower_vmaf=$((target_vmaf - 2))
    cmd=(
        ab-av1 auto-encode
        --input "$segment"
        --output "$output_segment"
        --encoder libsvtav1
        --min-vmaf "$lower_vmaf"
        --preset "${PRESET}"
        --svt "tune=0:film-grain=0:film-grain-denoise=0"
        --keyint 10s
        --samples "${VMAF_SAMPLE_COUNT}"
        --sample-duration "${VMAF_SAMPLE_LENGTH}s"
        --vmaf "n_subsample=8:pool=harmonic_mean"
        --quiet
    )
    
    if [[ -n "$crop_filter" ]]; then
        cmd+=(--vfilter "crop=$crop_filter")
    fi
    
    echo "Final attempt with lower VMAF target: ${cmd[*]}" >&2
    
    if "${cmd[@]}"; then
        print_check "Successfully encoded segment with lower VMAF: $(basename "$segment")"
        return 0
    fi
    
    error "Failed to encode segment after all attempts: $(basename "$segment")"
    return 1
}
""")
            bash_script.close()
            os.chmod(bash_script.name, 0o755)
            
            # Build command list
            segment_count = 0
            for segment in sorted(segments_dir.glob("*.mkv")):
                output_segment = encoded_dir / segment.name
                
                # Skip if already encoded
                if output_segment.exists() and output_segment.stat().st_size > 0:
                    logger.info(f"Segment already encoded: {segment.name}")
                    continue
                    
                # Build command with proper quoting
                cmd = f"source {bash_script.name} && encode_single_segment '{segment}' '{output_segment}' '{self.config.target_vmaf}' '{crop_filter or ''}'"
                cmd_file.write(cmd + "\n")
                segment_count += 1
            
            cmd_file.close()
            
            if segment_count == 0:
                logger.error("No segments found to encode")
                return
            
            # Find parallel executable
            parallel_path = shutil.which("parallel")
            if not parallel_path:
                raise RuntimeError("GNU Parallel not found in PATH")
            
            # Set up environment variables
            env = os.environ.copy()
            env.update({
                'PRESET': str(self.config.preset),
                'VMAF_SAMPLE_COUNT': str(self.config.vmaf_sample_count),
                'VMAF_SAMPLE_LENGTH': str(self.config.vmaf_sample_length)
            })
            
            try:
                # Run parallel encoding
                logger.info("Starting parallel encoding...")
                parallel_cmd = [
                    parallel_path,
                    "--no-notice",
                    "--line-buffer",
                    "--halt", "soon,fail=1",
                    "--jobs", str(os.cpu_count() or 1),
                    "--will-cite",
                    "--bar",
                    "--eta",
                    "--progress",
                    "--joblog", str(encoded_dir / "parallel.log"),
                    "--env", "PRESET",
                    "--env", "VMAF_SAMPLE_COUNT",
                    "--env", "VMAF_SAMPLE_LENGTH",
                    "--",
                    "bash", "-c"
                ]
                
                # First try to run one command directly to check for issues
                with open(cmd_file.name, 'r') as f:
                    test_cmd = f.readline().strip()
                    logger.info("Testing encoding parameters with first segment...")
                    try:
                        subprocess.run(["bash", "-c", test_cmd], check=True, env=env)
                        logger.info("Test encode successful, proceeding with parallel encoding")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Test encode failed: {e}")
                        raise
                
                # Run parallel encoding
                with open(cmd_file.name, 'r') as f:
                    try:
                        subprocess.run(parallel_cmd, stdin=f, check=True, env=env)
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Parallel encoding failed: {e}")
                        # If parallel fails, try sequential encoding
                        logger.warning("Falling back to sequential encoding")
                        f.seek(0)  # Reset file pointer
                        for cmd in f:
                            subprocess.run(["bash", "-c", cmd.strip()], check=True, env=env)
            except subprocess.CalledProcessError as e:
                # If parallel fails, try sequential encoding
                logger.warning(f"Parallel encoding failed ({e}), falling back to sequential encoding")
                try:
                    with open(cmd_file.name, 'r') as f:
                        for cmd in f:
                            subprocess.run(["bash", "-c", cmd.strip()], check=True, env=env)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to encode segments: {e}")
                    raise
                    
        finally:
            # Cleanup
            try:
                os.unlink(cmd_file.name)
                os.unlink(bash_script.name)
            except OSError:
                pass
        
        # Validate the encoded segments
        self._validate_encoded_segments(segments_dir, encoded_dir)
        
        logger.info("Successfully encoded segments")

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

    def encode_dolby_vision(self, input_file: Path, output_file: Path) -> None:
        """Encode Dolby Vision content using FFmpeg and libsvtav1.
        
        Args:
            input_file: Input video file
            output_file: Output video file
        """
        with self.work_manager.work_space(output_file) as work_dirs:
            try:
                # Set up file paths
                audio_file = work_dirs['audio'] / "audio.opus"
                video_file = work_dirs['root'] / "video.mkv"
                
                # Process audio first
                audio_info = self.audio_processor.get_audio_info(input_file)
                if audio_info:
                    self.fmt.print_audio_status(
                        0,  # track number
                        audio_info['channels'],
                        audio_info['layout'],
                        audio_info['bitrate']
                    )
                
                # Build audio FFmpeg command
                audio_cmd = [
                    str(self.config.ffmpeg),
                    "-hide_banner",
                    "-loglevel", "info",
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
                    str(audio_file)
                ]
                
                # Print audio FFmpeg command
                logger.info("FFmpeg command for audio encoding:")
                logger.info("\n" + self._format_ffmpeg_command(audio_cmd))
                
                if not self.audio_processor.encode_audio(input_file, audio_file, work_dirs['audio']):
                    logger.error("Failed to encode audio")
                    raise RuntimeError("Audio encoding failed")
                
                # Validate audio
                if not self.audio_processor.validate_audio(audio_file):
                    logger.error("Audio validation failed")
                    raise RuntimeError("Audio validation failed")
                
                # Build FFmpeg command for Dolby Vision encoding
                width = self.get_video_width(input_file)
                if width >= 3840:
                    crf = self.config.crf_uhd
                    self.fmt.print_check(f"UHD quality detected ({width}px width), using CRF {crf}")
                elif width >= 1920:
                    crf = self.config.crf_hd
                    self.fmt.print_check(f"HD quality detected ({width}px width), using CRF {crf}")
                else:
                    crf = self.config.crf_sd
                    self.fmt.print_check(f"SD quality detected ({width}px width), using CRF {crf}")
                
                # Get hardware acceleration options
                hw_accel = self._configure_hw_accel()
                
                # Construct video FFmpeg command
                video_cmd = [
                    str(self.config.ffmpeg),
                    "-hide_banner",
                    "-loglevel", "warning",
                ]
                
                # Add hardware acceleration if configured
                if hw_accel:
                    video_cmd.extend(hw_accel)
                
                # Add input and encoding options
                video_cmd.extend([
                    "-i", str(input_file),
                    "-map", "0:v:0",
                    "-c:v", "libsvtav1",
                    "-preset", str(self.config.preset),
                    "-crf", str(crf),
                    "-vf", "format=yuv420p10le",
                    "-color_primaries", "bt2020",
                    "-color_trc", "smpte2084",
                    "-colorspace", "bt2020nc",
                    "-svtav1-params",
                    f"tune=0:film-grain=8:film-grain-denoise=0:enable-hdr=1:enable-qm=1",
                    "-stats",
                    "-y",
                    str(video_file)
                ])
                
                # Print video FFmpeg command
                self.fmt.print_check("FFmpeg command for video encoding:")
                self.fmt.print_check(self._format_ffmpeg_command(video_cmd))
                
                # Run FFmpeg
                subprocess.run(video_cmd, check=True)
                
                # Mux final output
                self._mux_final_output(video_file, audio_file, input_file, output_file)
                
            except Exception as e:
                logger.error(f"Error processing video: {e}")
                raise

    def get_video_width(self, input_file: Path) -> int:
        """Get video width from input file.
        
        Args:
            input_file: Input video file
            
        Returns:
            Video width in pixels
        """
        try:
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width',
                    '-of', 'default=noprint_wrappers=1:nokey=1',
                    str(input_file)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return int(result.stdout.strip())
            
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Failed to get video width: {e}")
            return 1920  # Default to HD resolution

    def _mux_final_output(self, video_file: Path, audio_file: Path, input_file: Path, output_file: Path) -> None:
        """Mux video, audio, subtitles and chapters into final output.
        
        Args:
            video_file: Encoded video file
            audio_file: Encoded audio file
            input_file: Original input file (for subtitles)
            output_file: Output file path
        """
        try:
            # Basic muxing command
            cmd = [
                'ffmpeg', '-hide_banner', '-loglevel', 'info',
                '-i', str(video_file),   # Video stream
                '-i', str(audio_file),   # Audio stream
                '-i', str(input_file),   # Original file for subtitles
                '-map', '0:v:0',         # Map video from first input
                '-map', '1:a?',          # Map all audio from second input
                '-map', '2:s?',          # Map all subtitles from original if present
                '-map', '2:t?',          # Map all attachments if present
                '-c:v', 'copy',          # Copy video stream
                '-c:a', 'copy',          # Copy audio stream (preserve opus)
                '-c:s', 'copy',          # Copy subtitles
                '-c:t', 'copy',          # Copy attachments
                str(output_file)
            ]
            logger.info("\nFFmpeg command for muxing tracks:")
            logger.info("\n" + self._format_ffmpeg_command(cmd))
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("Successfully muxed final output")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to mux final output: {e}")
            if e.stderr:
                logger.error(f"FFmpeg error output: {e.stderr}")
            raise

class VideoEncoder:
    """Video encoder."""
    
    def __init__(self, config: 'EncodingConfig'):
        """Initialize video encoder.
        
        Args:
            config: Encoding configuration
        """
        self.config = config
