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

from loguru import logger

from .encoder import VideoEncoder
from .segment_handler import SegmentHandler
from .formatting import TerminalFormatter
from .audio_processor import AudioProcessor

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
        self.audio_processor = AudioProcessor()
        self.stream_sizes: Dict[str, int] = {}
        self._active_work_dirs: Set[Path] = set()
        
        # Register cleanup handlers
        atexit.register(self._cleanup_work_dirs)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Set up process group to handle child processes
        os.setpgrp()

    def _signal_handler(self, signum, frame):
        """Handle interruption signals by cleaning up work directories."""
        logger.info(f"Received signal {signum}, cleaning up...")
        try:
            # Try to terminate any child processes in our process group
            if signum in (signal.SIGINT, signal.SIGTERM):
                os.killpg(os.getpgid(0), signum)
        except Exception as e:
            logger.error(f"Error terminating child processes: {e}")
            
        self._cleanup_work_dirs()
        # Re-raise the signal
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    def _cleanup_work_dirs(self) -> None:
        """Clean up all active work directories."""
        for work_dir in self._active_work_dirs:
            try:
                shutil.rmtree(work_dir)
            except Exception as e:
                logger.error(f"Failed to clean up work directory {work_dir}: {e}")

    def process_video(self, input_file: Path, output_file: Path) -> None:
        """Process a video file.
        
        Args:
            input_file: Input video file
            output_file: Output video file
        """
        # Convert paths to absolute
        input_abs = input_file.resolve()
        output_abs = output_file.resolve()
        
        logger.debug(f"Processing video: input={input_abs}, output={output_abs}")
        
        logger.info(f"Processing video: {input_abs}")
        
        # Detect Dolby Vision
        is_dolby_vision = self.detect_dolby_vision(input_abs)
        
        if is_dolby_vision:
            logger.info("Using FFmpeg directly for Dolby Vision content")
            self.encode_dolby_vision(input_abs, output_abs)
        else:
            # Use configured working_dir if set, otherwise create in output dir
            if self.config.working_dir:
                work_dir = Path(self.config.working_dir) / f"{output_abs.stem}_work"
            else:
                work_dir = output_abs.parent / f"{output_abs.stem}_work"
            
            # Ensure work directory is empty before starting
            if work_dir.exists():
                logger.info(f"Cleaning up existing work directory {work_dir}...")
                try:
                    shutil.rmtree(work_dir)
                except Exception as e:
                    logger.error(f"Failed to clean up existing work directory: {e}")
                    
            work_dir.mkdir(parents=True, exist_ok=True)
            self._active_work_dirs.add(work_dir)
            
            try:
                # Set up directories
                segments_dir = work_dir / "segments"
                encoded_segments_dir = work_dir / "encoded"
                audio_file = work_dir / "audio.opus"
                video_file = work_dir / "video.mkv"
                
                # Encode audio first
                if not self.audio_processor.encode_audio(input_abs, audio_file):
                    logger.error("Failed to encode audio")
                    raise RuntimeError("Audio encoding failed")
                
                # Validate audio
                if not self.audio_processor.validate_audio(audio_file):
                    logger.error("Audio validation failed")
                    raise RuntimeError("Audio validation failed")

                # Get crop filter
                crop_filter = self.detect_crop(input_abs) if not self.config.disable_crop else None
                
                # Segment video
                self.segment_handler.segment_video(input_abs, segments_dir)
                
                # Encode segments
                self._encode_segments(segments_dir, encoded_segments_dir, crop_filter)
                
                # Validate encoded segments
                self.segment_handler.validate_segments(encoded_segments_dir)
                
                # Concatenate video segments
                self.segment_handler.concatenate_segments(encoded_segments_dir, video_file)
                
                # Mux final output
                self._mux_final_output(video_file, audio_file, input_abs, output_abs)
                
            except Exception as e:
                logger.error(f"Error processing video: {e}")
                raise
            finally:
                # Remove this work directory from active set and clean it up
                self._active_work_dirs.discard(work_dir)
                if work_dir.exists():
                    logger.info(f"Cleaning up {work_dir}...")
                    try:
                        shutil.rmtree(work_dir)
                        logger.info("Cleanup completed")
                    except Exception as e:
                        logger.error(f"Failed to clean up work directory: {e}")
                        # Try to clean up with a shell command as fallback
                        try:
                            subprocess.run(['rm', '-rf', str(work_dir)], check=True)
                            logger.info("Cleanup completed using rm command")
                        except subprocess.CalledProcessError as e:
                            logger.error(f"Failed to clean up work directory using rm command: {e}")
                    
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
        success_count = 0
        
        # Process each video
        for video_file in video_files:
            rel_path = video_file.relative_to(input_dir)
            output_file = output_dir / rel_path.with_suffix('.mkv')
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            self.fmt.print_check(f"\nProcessing {rel_path}")
            self.process_video(video_file, output_file)
            success_count += 1
                
        # Print summary
        if success_count == len(video_files):
            self.fmt.print_success(f"\nSuccessfully processed all {success_count} videos")
            return True
        else:
            self.fmt.print_error(f"\nProcessed {success_count} out of {len(video_files)} videos")
            return False

    def detect_crop(self, input_file: Path) -> Optional[str]:
        """Detect black bars and return crop filter.
        
        Args:
            input_file: Input video file
            
        Returns:
            Crop filter string if black bars detected, None otherwise
        """
        try:
            logger.info("Analyzing video for black bars...")
            
            # Check if input is HDR and get color properties
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=color_transfer,color_primaries,color_space',
                    '-of', 'csv=p=0',
                    str(input_file)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            color_props = result.stdout.strip().split(',')
            if len(color_props) != 3:
                return None
                
            color_transfer, color_primaries, color_space = color_props
            
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
                color_transfer in hdr_formats or
                color_primaries in hdr_formats or
                color_space in hdr_formats
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
                    if crop not in crop_values:
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

    def detect_dolby_vision(self, input_file: Path) -> bool:
        """Detect if file contains Dolby Vision.
        
        Args:
            input_file: Input video file
            
        Returns:
            True if Dolby Vision is detected
        """
        try:
            result = subprocess.run(
                ['mediainfo', str(input_file)],
                capture_output=True,
                text=True,
                check=True
            )
            
            if 'Dolby Vision' in result.stdout:
                logger.info("Dolby Vision detected")
                return True
                
            return False
            
        except subprocess.CalledProcessError as e:
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
set -e

# Helper functions
print_check() { echo "✓ $*" >&2; }
error() { echo "✗ $*" >&2; }

encode_single_segment() {
    local segment="$1"
    local output_segment="$2"
    local target_vmaf="$3"
    local crop_filter="$4"
    
    # Build base command
    local cmd=(
        ab-av1 auto-encode
        --input "$segment"
        --output "$output_segment"
        --encoder libsvtav1
        --min-vmaf "$target_vmaf"
        --preset "$PRESET"
        --svt "tune=0:film-grain=0:film-grain-denoise=0"
        --keyint 10s
        --samples "$VMAF_SAMPLE_COUNT"
        --sample-duration "${VMAF_SAMPLE_LENGTH}s"
        --vmaf "n_subsample=8:pool=harmonic_mean"
        --quiet
    )
    
    # Add crop filter if provided
    if [[ -n "$crop_filter" ]]; then
        cmd+=(--vfilter "crop=$crop_filter")
    fi
    
    # First attempt with default settings
    if "${cmd[@]}"; then
        return 0
    fi
    
    # Second attempt with more samples
    cmd=(
        ab-av1 auto-encode
        --input "$segment"
        --output "$output_segment"
        --encoder libsvtav1
        --min-vmaf "$target_vmaf"
        --preset "$PRESET"
        --svt "tune=0:film-grain=0:film-grain-denoise=0"
        --keyint 10s
        --samples 6
        --sample-duration "2s"
        --vmaf "n_subsample=8:pool=harmonic_mean"
        --quiet
    )
    
    if [[ -n "$crop_filter" ]]; then
        cmd+=(--vfilter "crop=$crop_filter")
    fi
    
    if "${cmd[@]}"; then
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
        --preset "$PRESET"
        --svt "tune=0:film-grain=0:film-grain-denoise=0"
        --keyint 10s
        --samples 6
        --sample-duration "2s"
        --vmaf "n_subsample=8:pool=harmonic_mean"
        --quiet
    )
    
    if [[ -n "$crop_filter" ]]; then
        cmd+=(--vfilter "crop=$crop_filter")
    fi
    
    if "${cmd[@]}"; then
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
            for segment in segments_dir.glob("*.mkv"):
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
                    "--jobs", "0",
                    "--will-cite",
                    "--bar",
                    "--eta",
                    "::::","{}".format(cmd_file.name)
                ]
                
                # First try to run one command directly to check for issues
                with open(cmd_file.name, 'r') as f:
                    test_cmd = f.readline().strip()
                    logger.debug(f"Testing first command: {test_cmd}")
                    subprocess.run(["bash", "-c", test_cmd], check=True, env=env)
                
                # Run parallel encoding
                subprocess.run(parallel_cmd, check=True, env=env)
                
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

    def encode_dolby_vision(self, input_file: Path, output_file: Path) -> None:
        """Encode Dolby Vision content using FFmpeg and libsvtav1.
        
        Args:
            input_file: Input video file
            output_file: Output video file
        """
        # Create working directory
        work_dir = output_file.parent / f"{output_file.stem}_work"
        
        # Clean up existing work directory if it exists
        if work_dir.exists():
            logger.info(f"Cleaning up existing work directory {work_dir}...")
            try:
                shutil.rmtree(work_dir)
            except Exception as e:
                logger.error(f"Failed to clean up existing work directory: {e}")
                try:
                    subprocess.run(['rm', '-rf', str(work_dir)], check=True)
                    logger.info("Cleanup completed using rm command")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to clean up work directory using rm command: {e}")
                    raise RuntimeError("Failed to clean up existing work directory")
        
        work_dir.mkdir(parents=True, exist_ok=True)
        self._active_work_dirs.add(work_dir)
        
        try:
            # Set up audio file
            audio_file = work_dir / "audio.opus"
            
            # Encode audio first
            if not self.audio_processor.encode_audio(input_file, audio_file):
                logger.error("Failed to encode audio")
                raise RuntimeError("Audio encoding failed")
            
            # Validate audio
            if not self.audio_processor.validate_audio(audio_file):
                logger.error("Audio validation failed")
                raise RuntimeError("Audio validation failed")

            # Get video width for CRF selection
            width = self.get_video_width(input_file)
            
            # Set CRF based on resolution
            if width > 1920:
                crf = self.config.crf_uhd
                logger.info(f"UHD quality detected ({width}px width), using CRF {crf}")
            elif width > 1280:
                crf = self.config.crf_hd
                logger.info(f"HD quality detected ({width}px width), using CRF {crf}")
            else:
                crf = self.config.crf_sd
                logger.info(f"SD quality detected ({width}px width), using CRF {crf}")

            # Basic video options
            video_opts = [
                '-c:v', 'libsvtav1',
                '-preset', str(self.config.preset),
                '-crf', str(crf),
                '-svtav1-params', self.config.svt_params,
                '-dolbyvision', 'true'
            ]
            
            # Get crop filter
            crop_filter = self.detect_crop(input_file) if not self.config.disable_crop else None
            
            # Add crop filter if enabled
            if crop_filter:
                video_opts.extend(['-vf', crop_filter])

            # Copy subtitles
            video_opts.extend(['-c:s', 'copy'])
            
            # Create temporary video file
            video_file = work_dir / "video.mkv"
            
            # Run FFmpeg for video
            subprocess.run(
                [
                    self.config.ffmpeg, '-hide_banner', '-loglevel', 'info',
                    '-i', str(input_file),
                    *video_opts,
                    str(video_file)
                ],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Mux final output
            self._mux_final_output(video_file, audio_file, input_file, output_file)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to encode Dolby Vision content: {e}")
            if e.stderr:
                logger.error(f"FFmpeg error output: {e.stderr}")
            raise
        finally:
            # Remove this work directory from active set and clean it up
            self._active_work_dirs.discard(work_dir)
            if work_dir.exists():
                logger.info(f"Cleaning up {work_dir}...")
                try:
                    shutil.rmtree(work_dir)
                    logger.info("Cleanup completed")
                except Exception as e:
                    logger.error(f"Failed to clean up work directory: {e}")
                    # Try to clean up with a shell command as fallback
                    try:
                        subprocess.run(['rm', '-rf', str(work_dir)], check=True)
                        logger.info("Cleanup completed using rm command")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to clean up work directory using rm command: {e}")
                    
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
