"""Video segmentation and concatenation module."""

import subprocess
from pathlib import Path
from typing import Optional, List

from loguru import logger

from .formatting import TerminalFormatter


class SegmentHandler:
    """Handle video segmentation and concatenation."""
    
    def __init__(self, config: 'EncodingConfig'):
        """Initialize segment handler.
        
        Args:
            config: Encoding configuration
        """
        self.config = config
        self.fmt = TerminalFormatter()
        
    def segment_video(self, input_file: Path, output_dir: Path) -> bool:
        """Segment video into chunks.
        
        Args:
            input_file: Input video file
            output_dir: Output directory for segments
            
        Returns:
            True if segmentation was successful
        """
        self.fmt.print_check("Segmenting video...")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Segment video using ffmpeg
            cmd = [
                str(self.config.ffmpeg),
                '-hide_banner',
                '-loglevel', 'error',
                '-i', str(input_file),
                '-map', '0:v:0',  # Only copy first video stream
                '-c:v', 'copy',  # Copy stream without re-encoding
                '-an',  # No audio
                '-f', 'segment',
                '-segment_time', str(self.config.segment_length),
                '-reset_timestamps', '1',
                str(output_dir / '%04d.mkv')
            ]
            
            subprocess.run(cmd, check=True)
            
            # Validate segments
            if not self.validate_segments(output_dir):
                self.fmt.print_error("Failed to validate segments")
                return False
                
            return True
            
        except subprocess.CalledProcessError as e:
            self.fmt.print_error(f"Error segmenting video: {str(e)}")
            return False
            
    def concatenate_segments(self, input_dir: Path, output_file: Path) -> bool:
        """Concatenate encoded segments.
        
        Args:
            input_dir: Directory containing encoded segments
            output_file: Output video file
            
        Returns:
            True if concatenation was successful
        """
        self.fmt.print_check("Concatenating segments...")
        try:
            # Create concat file
            concat_file = input_dir / 'concat.txt'
            with open(concat_file, 'w') as f:
                for segment in sorted(input_dir.glob('*.mkv')):
                    if segment.name != 'concat.txt':
                        f.write(f"file '{segment.name}'\n")
                        
            # Concatenate segments
            cmd = [
                str(self.config.ffmpeg), '-hide_banner', '-loglevel', 'error',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                str(output_file)
            ]
            
            subprocess.run(cmd, check=True)
            concat_file.unlink()  # Clean up concat file
            
            self.fmt.print_success("Successfully concatenated segments")
            return True
            
        except (subprocess.CalledProcessError, IOError) as e:
            self.fmt.print_error(f"Error concatenating segments: {str(e)}")
            return False
            
    def validate_segments(self, input_dir: Path) -> bool:
        """Validate encoded segments.
        
        Args:
            input_dir: Directory containing encoded segments
            
        Returns:
            True if all segments are valid
        """
        self.fmt.print_check("Validating segments...")
        try:
            logger.debug(f"Checking for segments in directory: {input_dir}")
            logger.debug(f"Directory exists: {input_dir.exists()}")
            if input_dir.exists():
                logger.debug(f"Directory contents: {list(input_dir.iterdir())}")

            # Count segments
            segments = self.get_segments(input_dir)
            segment_count = len(segments)
            logger.debug(f"Found {segment_count} .mkv segments")
            
            # Also check for other video formats
            for ext in ['.mp4', '.webm', '.av1']:
                other_segments = list(input_dir.glob(f'*{ext}'))
                if other_segments:
                    logger.debug(f"Found {len(other_segments)} {ext} files: {other_segments}")
            
            if segment_count < 1:
                self.fmt.print_error("No segments found")
                return False
                
            # Check each segment
            min_file_size = 1024  # 1KB minimum file size
            invalid_segments = 0
            
            for segment in segments:
                # Check file size
                if segment.stat().st_size < min_file_size:
                    self.fmt.print_error(f"Segment too small: {segment.name}")
                    invalid_segments += 1
                    continue
                    
                # Check if file is valid
                try:
                    cmd = [str(self.config.ffprobe), '-v', 'error', str(segment)]
                    subprocess.run(cmd, check=True, capture_output=True)
                except subprocess.CalledProcessError:
                    self.fmt.print_error(f"Invalid segment: {segment.name}")
                    invalid_segments += 1
                    
            if invalid_segments > 0:
                self.fmt.print_error(f"Found {invalid_segments} invalid segments")
                return False
                
            self.fmt.print_success(f"Successfully validated {segment_count} segments")
            return True
            
        except subprocess.CalledProcessError as e:
            self.fmt.print_error(f"Error validating segments: {e.stderr.decode() if e.stderr else str(e)}")
            return False
            
    def get_segments(self, directory: Path) -> List[Path]:
        """Get list of .mkv segments in directory.
        
        Args:
            directory: Directory to search in
            
        Returns:
            List of paths to .mkv segments
        """
        if not directory.exists():
            return []
            
        # Get all .mkv files but filter out macOS system files
        segments = [p for p in directory.glob('*.mkv') if not p.name.startswith('._')]
        segments.sort()  # Ensure consistent ordering
        return segments

    def _get_duration(self, input_file: Path) -> float:
        """Get video duration in seconds.
        
        Args:
            input_file: Input video file
            
        Returns:
            Duration in seconds, or 0 if error
        """
        try:
            cmd = [
                str(self.config.ffprobe),
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(input_file)
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return float(result.stdout.strip())
            
        except (subprocess.CalledProcessError, ValueError) as e:
            self.fmt.print_error(f"Error getting video duration: {str(e)}")
            return 0.0
