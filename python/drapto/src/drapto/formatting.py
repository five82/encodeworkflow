"""Terminal formatting module."""

import os
import sys
from typing import Optional
from datetime import datetime
from pathlib import Path


class TerminalFormatter:
    """Terminal formatting class."""
    
    def __init__(self):
        """Initialize terminal formatter."""
        self.has_color = self._check_color_support()
        
        # Basic formatting
        self.bold = "\033[1m" if self.has_color else ""
        self.reset = "\033[0m" if self.has_color else ""
        
        # Basic colors
        self.green = "\033[32m" if self.has_color else ""
        self.yellow = "\033[33m" if self.has_color else ""
        self.blue = "\033[34m" if self.has_color else ""
        self.magenta = "\033[35m" if self.has_color else ""
        self.cyan = "\033[36m" if self.has_color else ""
        self.white = "\033[37m" if self.has_color else ""
        self.red = "\033[31m" if self.has_color else ""
        
        # Bold + color combinations
        self.bold_green = f"{self.bold}{self.green}" if self.has_color else ""
        self.bold_yellow = f"{self.bold}{self.yellow}" if self.has_color else ""
        self.bold_blue = f"{self.bold}{self.blue}" if self.has_color else ""
        self.bold_magenta = f"{self.bold}{self.magenta}" if self.has_color else ""
        self.bold_cyan = f"{self.bold}{self.cyan}" if self.has_color else ""
        self.bold_white = f"{self.bold}{self.white}" if self.has_color else ""
        self.bold_red = f"{self.bold}{self.red}" if self.has_color else ""
        
    def _check_color_support(self) -> bool:
        """Check if terminal supports colors.
        
        Returns:
            True if terminal supports colors
        """
        # Check if output is a terminal
        if not sys.stdout.isatty():
            return False
            
        # Check for NO_COLOR environment variable
        if os.environ.get("NO_COLOR"):
            return False
            
        # Check for TERM environment variable
        term = os.environ.get("TERM", "").lower()
        if term in ["dumb", "unknown"]:
            return False
            
        return True
        
    def print_check(self, message: str) -> None:
        """Print a checkmark message in green.
        
        Args:
            message: Message to print
        """
        print(f"{self.bold_green}✓{self.reset} {self.bold}{message}{self.reset}", file=sys.stderr)
        
    def print_warning(self, message: str) -> None:
        """Print a warning message in yellow.
        
        Args:
            message: Message to print
        """
        print(f"{self.bold_yellow}⚠{self.reset} {self.bold}{message}{self.reset}", file=sys.stderr)
        
    def print_error(self, message: str) -> None:
        """Print an error message in red.
        
        Args:
            message: Message to print
        """
        print(f"{self.bold_red}✗{self.reset} {self.bold}{message}{self.reset}", file=sys.stderr)
        
    def print_success(self, message: str) -> None:
        """Print a success message in green.
        
        Args:
            message: Message to print
        """
        print(f"{self.green}✓{self.reset} {self.green}{message}{self.reset}", file=sys.stderr)
        
    def print_header(self, title: str) -> None:
        """Print a section header.
        
        Args:
            title: Header title
        """
        print()
        print(f"{self.bold_blue}{'=' * 80}{self.reset}")
        print(f"{self.bold_blue}{title:^80}{self.reset}")
        print(f"{self.bold_blue}{'=' * 80}{self.reset}")
        print()
        
    def print_separator(self) -> None:
        """Print a separator line."""
        print(f"{self.blue}{'-' * 40}{self.reset}")
        
    def print_path(self, path: str) -> None:
        """Print a file path with highlighting.
        
        Args:
            path: Path to print
        """
        print(f"{self.bold_cyan}{path}{self.reset}")
        
    def print_stat(self, stat: str) -> None:
        """Print a statistic or measurement.
        
        Args:
            stat: Statistic to print
        """
        print(f"{self.bold_magenta}{stat}{self.reset}")
        
    def format_size(self, size: int) -> str:
        """Format file size for display.
        
        Args:
            size: Size in bytes
            
        Returns:
            Formatted size string
        """
        suffixes = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
        scale = 0
        
        while size > 1024 and scale < len(suffixes) - 1:
            size /= 1024
            scale += 1
            
        return f"{size:.1f} {suffixes[scale]}"
        
    def print_ffmpeg_info(self, ffmpeg_path: str, ffprobe_path: str, is_system: bool = False) -> None:
        """Print ffmpeg binary information.
        
        Args:
            ffmpeg_path: Path to ffmpeg
            ffprobe_path: Path to ffprobe
            is_system: Whether using system binaries
        """
        if is_system:
            print("Local ffmpeg/ffprobe not found.")
            print(f"Using system ffmpeg: {ffmpeg_path}")
            print(f"Using system ffprobe: {ffprobe_path}")
        else:
            print(f"Using local ffmpeg binary: {ffmpeg_path}")
            print(f"Using local ffprobe binary: {ffprobe_path}")
            
    def print_encode_start(self, input_file: str, output_file: str) -> None:
        """Print encode start header.
        
        Args:
            input_file: Input file path
            output_file: Output file path
        """
        self.print_header("Starting Encode")
        print(f"Input file:  {input_file}")
        print(f"Output file: {output_file}")
        self.print_separator()
        print(f"Processing: {Path(input_file).name}")
        
    def print_dolby_check(self, has_dolby: bool) -> None:
        """Print Dolby Vision check status.
        
        Args:
            has_dolby: Whether Dolby Vision was detected
        """
        self.print_check("Checking for Dolby Vision...")
        if has_dolby:
            self.print_check("Dolby Vision detected")
            self.print_check("Using FFmpeg with SVT-AV1 for Dolby Vision encoding...")
        else:
            self.print_check("Dolby Vision not detected")
            self.print_check("Using chunked encoding with ab-av1...")
            
    def print_black_bar_analysis(self, frame_count: int, bar_pixels: Optional[int] = None) -> None:
        """Print black bar analysis status.
        
        Args:
            frame_count: Number of frames analyzed
            bar_pixels: Number of black bar pixels found
        """
        self.print_check("Analyzing video for black bars...")
        self.print_check(f"Analyzing {frame_count} frames for black bars...")
        if bar_pixels is not None:
            self.print_check(f"Found black bars: {bar_pixels} pixels ({(bar_pixels/1080)*100:.0f}% of height)")
            
    def print_segment_status(self, segment_count: int) -> None:
        """Print segment validation status.
        
        Args:
            segment_count: Number of segments validated
        """
        self.print_check("Segmenting video...")
        self.print_check("Validating segments...")
        self.print_check(f"Successfully validated {segment_count} segments")
        
    def print_audio_status(self, track_num: int, channels: int, layout: str, bitrate: int) -> None:
        """Print audio processing status.
        
        Args:
            track_num: Audio track number
            channels: Number of audio channels
            layout: Channel layout
            bitrate: Audio bitrate
        """
        self.print_check(f"Processing audio track {track_num}...")
        self.print_check(f"Found {channels} audio channels")
        self.print_check(f"Configured audio stream {track_num}: {channels} channels, {layout} layout, {bitrate}k bitrate")
        self.print_check("Using codec: libopus (VBR mode, compression level 10)")
        
    def print_encode_progress(self, percent: float, encoded_size: str) -> None:
        """Print encoding progress.
        
        Args:
            percent: Progress percentage
            encoded_size: Size of encoded data
        """
        print(f"Encoded {encoded_size} ({percent:.0f}%)")
        
    def print_encode_summary(self, input_size: int, output_size: int, encode_time: str, filename: str) -> None:
        """Print encoding summary for a file.
        
        Args:
            input_size: Input file size in bytes
            output_size: Output file size in bytes
            encode_time: Encoding time string
            filename: Name of processed file
        """
        reduction = ((input_size - output_size) / input_size) * 100
        
        self.print_header("Encoding Summary")
        print(f"Input size:  {self.format_size(input_size)}")
        print(f"Output size: {self.format_size(output_size)}")
        print(f"Reduction:   {reduction:.2f}%")
        self.print_separator()
        print(f"Completed: {filename}")
        print(f"Encoding time: {encode_time}")
        print(f"Finished encode at {datetime.now().strftime('%a %b %d %I:%M:%S %p %Z %Y')}")
        self.print_separator()
        
    def print_final_summary(self, files: list[tuple[str, int, int, str]]) -> None:
        """Print final encoding summary for all files.
        
        Args:
            files: List of (filename, input_size, output_size, encode_time) tuples
        """
        self.print_header("Final Encoding Summary")
        
        total_time = 0
        for filename, input_size, output_size, encode_time in files:
            reduction = ((input_size - output_size) / input_size) * 100
            self.print_separator()
            print(f"File: {filename}")
            print(f"Input size:  {self.format_size(input_size)}")
            print(f"Output size: {self.format_size(output_size)}")
            print(f"Reduction:   {reduction:.2f}%")
            print(f"Encode time: {encode_time}")
            
            # Add encode time to total
            time_parts = encode_time.split()
            hours = int(time_parts[0][:-1]) if 'h' in time_parts[0] else 0
            minutes = int(time_parts[1][:-1]) if 'm' in time_parts[1] else 0
            seconds = int(time_parts[2][:-1]) if 's' in time_parts[2] else 0
            total_time += hours * 3600 + minutes * 60 + seconds
            
        self.print_separator()
        hours = total_time // 3600
        minutes = (total_time % 3600) // 60
        seconds = total_time % 60
        print(f"Total execution time: {hours:02d}h {minutes:02d}m {seconds:02d}s")
