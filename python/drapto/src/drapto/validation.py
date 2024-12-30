"""Validation module."""

import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from loguru import logger

from .formatting import TerminalFormatter


class VideoValidator:
    """Video validator class."""
    
    def __init__(self, config: 'EncodingConfig'):
        """Initialize validator.
        
        Args:
            config: Encoding configuration
        """
        self.config = config
        self.fmt = TerminalFormatter()
        
    def validate_output(self, input_file: Path, output_file: Path) -> bool:
        """Validate the output file.
        
        Args:
            input_file: Input video file
            output_file: Output video file
            
        Returns:
            True if validation was successful
        """
        self.fmt.print_header("Validating Output")
        error = False
        
        # Check if file exists and has size
        if not output_file.exists() or output_file.stat().st_size == 0:
            self.fmt.print_error("Output file is empty or doesn't exist")
            return False
            
        # Check video stream
        video_stream = self._get_video_codec(output_file)
        if video_stream != "av1":
            self.fmt.print_error("No AV1 video stream found in output")
            error = True
        else:
            duration = self._get_duration(output_file)
            self.fmt.print_check(f"Video stream: AV1, Duration: {duration:.2f}s")
            
        # Check audio streams
        audio_count = self._get_audio_stream_count(output_file)
        if audio_count == 0:
            self.fmt.print_error("No Opus audio streams found in output")
            error = True
        else:
            self.fmt.print_check(f"Audio streams: {audio_count} Opus stream(s)")
            
        # Compare durations
        input_duration = self._get_duration(input_file)
        output_duration = self._get_duration(output_file)
        
        # Allow 1 second difference
        duration_diff = abs(input_duration - output_duration)
        if duration_diff > 1:
            self.fmt.print_error(
                f"Output duration ({output_duration:.2f}s) differs significantly "
                f"from input ({input_duration:.2f}s)"
            )
            error = True
            
        if error:
            self.fmt.print_error("Output validation failed")
            return False
            
        self.fmt.print_success("Output validation successful")
        return True
        
    def check_dependencies(self) -> bool:
        """Check for required dependencies.
        
        Returns:
            True if all dependencies are available
        """
        self.fmt.print_header("Checking Dependencies")
        
        # Check ffmpeg and ffprobe
        ffmpeg_path = self._check_ffmpeg()
        if not ffmpeg_path:
            self.fmt.print_error("FFmpeg not found")
            return False
            
        ffprobe_path = self._check_ffprobe()
        if not ffprobe_path:
            self.fmt.print_error("FFprobe not found")
            return False
            
        # Check mediainfo
        if not shutil.which("mediainfo"):
            self.fmt.print_error("MediaInfo not found")
            return False
            
        # Check GNU Parallel
        if not self._check_parallel():
            return False
            
        # Check ab-av1 if chunked encoding is enabled
        if self.config.enable_chunked_encoding:
            if not shutil.which("ab-av1"):
                self.fmt.print_error(
                    "ab-av1 is required for chunked encoding but not found. "
                    "Install with: cargo install ab-av1"
                )
                return False
                
        # Check platform-specific dependencies
        if self.config.is_macos:
            if not shutil.which("brew"):
                self.fmt.print_error("Homebrew is required on macOS")
                return False
        else:
            # Check for vainfo on Linux
            if not shutil.which("vainfo"):
                self.fmt.print_warning("vainfo not found, hardware acceleration may not be available")
                
        self.fmt.print_success("All required dependencies found")
        return True
        
    def _check_ffmpeg(self) -> Optional[str]:
        """Check for ffmpeg.
        
        Returns:
            Path to ffmpeg if found, None otherwise
        """
        # First check local ffmpeg
        local_ffmpeg = Path(self.config.ffmpeg)
        if local_ffmpeg.exists() and os.access(local_ffmpeg, os.X_OK):
            self.fmt.print_check(f"Using local ffmpeg: {local_ffmpeg}")
            return str(local_ffmpeg)
            
        # Then check system ffmpeg
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            self.fmt.print_check(f"Using system ffmpeg: {system_ffmpeg}")
            return system_ffmpeg
            
        return None
        
    def _check_ffprobe(self) -> Optional[str]:
        """Check for ffprobe.
        
        Returns:
            Path to ffprobe if found, None otherwise
        """
        # First check local ffprobe
        local_ffprobe = Path(self.config.ffprobe)
        if local_ffprobe.exists() and os.access(local_ffprobe, os.X_OK):
            self.fmt.print_check(f"Using local ffprobe: {local_ffprobe}")
            return str(local_ffprobe)
            
        # Then check system ffprobe
        system_ffprobe = shutil.which("ffprobe")
        if system_ffprobe:
            self.fmt.print_check(f"Using system ffprobe: {system_ffprobe}")
            return system_ffprobe
            
        return None
        
    def _check_parallel(self) -> bool:
        """Check for GNU Parallel.
        
        Returns:
            True if GNU Parallel is available
        """
        if not shutil.which("parallel"):
            self.fmt.print_error("GNU Parallel not found")
            
            # Print installation instructions
            if platform.system() == "Darwin" or platform.system() == "Linux":
                if shutil.which("brew"):
                    self.fmt.print_check("You can install GNU Parallel using Homebrew:")
                    self.fmt.print_path("    brew install parallel")
                else:
                    self.fmt.print_check("Homebrew is not installed. You can install it first:")
                    if platform.system() == "Darwin":
                        self.fmt.print_path(
                            "    /bin/bash -c \"$(curl -fsSL "
                            "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                        )
                    else:
                        self.fmt.print_path(
                            "    /bin/bash -c \"$(curl -fsSL "
                            "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
                        )
                        self.fmt.print_path(
                            "    (echo; echo 'eval \"$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)\"') "
                            ">> \"$HOME/.bashrc\""
                        )
                    self.fmt.print_check("Then install GNU Parallel:")
                    self.fmt.print_path("    brew install parallel")
            else:
                self.fmt.print_check("Please install GNU Parallel using your system's package manager")
                
            return False
            
        return True
        
    def _get_video_codec(self, file: Path) -> Optional[str]:
        """Get video codec from file.
        
        Args:
            file: Video file
            
        Returns:
            Video codec name if found
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "v",
                    "-show_entries", "stream=codec_name",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(file)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
            
    def _get_audio_stream_count(self, file: Path) -> int:
        """Get number of Opus audio streams in file.
        
        Args:
            file: Video file
            
        Returns:
            Number of Opus audio streams
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "a",
                    "-show_entries", "stream=codec_name",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(file)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip().count("opus")
        except subprocess.CalledProcessError:
            return 0
            
    def _get_duration(self, file: Path) -> float:
        """Get duration of file in seconds.
        
        Args:
            file: Video file
            
        Returns:
            Duration in seconds
        """
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(file)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return 0.0
