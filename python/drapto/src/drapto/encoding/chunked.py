"""Chunked encoder implementation for non-Dolby Vision content."""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from pydantic import BaseModel

from drapto.core.base import BaseEncoder, EncodingContext
from drapto.core.video.types import VideoStreamInfo
from drapto.core.video.analysis import VideoAnalyzer

class ChunkedEncoder(BaseEncoder):
    """Encoder that splits video into chunks for parallel processing."""
    
    def __init__(self, config):
        """Initialize encoder.
        
        Args:
            config: Encoder configuration
        """
        super().__init__(config)
        self._analyzer = VideoAnalyzer(config)
        self._logger = logging.getLogger(__name__)
        self._segment_length = config.get('segment_length', 10)  # Default 10s segments
        self._min_segment_size = 1024  # 1KB minimum segment size
        self._vmaf_target = config.get('vmaf_target', 95)
        self._vmaf_samples = config.get('vmaf_samples', 4)
        self._vmaf_duration = config.get('vmaf_duration', '1s')
        
    async def encode_content(self, context: EncodingContext) -> bool:
        """Encode content using chunked encoding.
        
        Args:
            context: Encoding context with input/output paths
            
        Returns:
            True if encoding successful, False otherwise
        """
        try:
            # Analyze input stream
            stream_info = self._analyzer.analyze_stream(context.input_path)
            if not stream_info:
                self._logger.error("Failed to analyze input stream")
                return False
                
            if stream_info.is_dolby_vision:
                self._logger.error("Cannot use chunked encoding for Dolby Vision content")
                return False
                
            # Create temporary directories
            with tempfile.TemporaryDirectory() as temp_dir:
                segments_dir = Path(temp_dir) / "segments"
                encoded_dir = Path(temp_dir) / "encoded"
                segments_dir.mkdir()
                encoded_dir.mkdir()
                
                # Segment the video
                if not await self._segment_video(context.input_path, segments_dir):
                    return False
                    
                # Validate segments
                if not await self._validate_segments(segments_dir):
                    return False
                    
                # Get quality settings
                crf, pix_fmt = self._analyzer.get_quality_settings(stream_info)
                
                # Detect black bars
                crop_filter = self._analyzer.detect_black_bars(context.input_path, stream_info)
                if crop_filter:
                    context.crop_filter = crop_filter
                    
                # Encode segments
                if not await self._encode_segments(segments_dir, encoded_dir, context, self._segment_length, pix_fmt):
                    return False
                    
                # Concatenate segments
                if not await self._concatenate_segments(encoded_dir, context.output_path):
                    return False
                    
                return True
                
        except Exception as e:
            self._logger.error(f"Encoding failed: {e}")
            return False
            
    async def _segment_video(self, input_path: Path, output_dir: Path) -> bool:
        """Split video into segments.
        
        Args:
            input_path: Input video path
            output_dir: Output directory for segments
            
        Returns:
            True if segmentation successful
        """
        try:
            cmd = [
                self.config.get('ffmpeg', 'ffmpeg'),
                '-hide_banner',
                '-loglevel', 'error',
                '-i', str(input_path),
                '-c:v', 'copy',
                '-an',
                '-f', 'segment',
                '-segment_time', str(self._segment_length),
                '-reset_timestamps', '1',
                str(output_dir / '%04d.mkv')
            ]
            
            self._logger.info(f"Segmenting video: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                self._logger.error(f"Segmentation failed: {stderr.decode()}")
                return False
                
            return True
            
        except Exception as e:
            self._logger.error(f"Segmentation failed: {e}")
            return False
            
    async def _validate_segments(self, segments_dir: Path) -> bool:
        """Validate video segments.
        
        Args:
            segments_dir: Directory containing segments
            
        Returns:
            True if all segments are valid
        """
        try:
            segments = list(segments_dir.glob('*.mkv'))
            if not segments:
                self._logger.error("No segments found")
                return False
                
            invalid_segments = []
            for segment in segments:
                # Check file size
                if segment.stat().st_size < self._min_segment_size:
                    invalid_segments.append(segment)
                    continue
                    
                # Verify segment can be read by ffprobe
                cmd = [
                    self.config.get('ffprobe', 'ffprobe'),
                    '-v', 'error',
                    str(segment)
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await proc.communicate()
                if proc.returncode != 0:
                    invalid_segments.append(segment)
                    
            if invalid_segments:
                self._logger.error(f"Found {len(invalid_segments)} invalid segments")
                return False
                
            self._logger.info(f"Successfully validated {len(segments)} segments")
            return True
            
        except Exception as e:
            self._logger.error(f"Segment validation failed: {e}")
            return False
            
    async def _encode_segments(
        self,
        input_dir: Path,
        output_dir: Path,
        context: EncodingContext,
        segment_duration: int,
        pixel_format: str
    ) -> bool:
        """Encode segments in parallel using GNU Parallel.
        
        Args:
            input_dir: Directory containing input segments
            output_dir: Directory for output segments
            context: Encoding context
            segment_duration: Duration of each segment in seconds
            pixel_format: Input pixel format
            
        Returns:
            True if encoding succeeded, False otherwise
        """
        try:
            parallel_path = shutil.which('parallel')
            if not parallel_path:
                self._logger.error("GNU Parallel not found")
                return False
                
            # Build parallel command
            cmd = [
                str(parallel_path),
                "--will-cite",  # Suppress citation notice
                "-j", str(os.cpu_count()),
                "ab-av1",
                "--input", "{}",
                "--output", str(output_dir / "{/.}.mkv"),
                "--vmaf-target", str(context.target_vmaf),
                "--preset", str(context.preset),
                "--svt-params", context.svt_params,
                "--pixel-format", pixel_format,
                "--segment-duration", str(segment_duration)
            ]
            
            if context.crop_filter:
                cmd.extend(["--crop", context.crop_filter])
                
            # Add input file pattern
            cmd.append(str(input_dir / "*.mkv"))
            
            self._logger.info("Starting parallel encode with %d threads", os.cpu_count())
            self._logger.debug("Parallel command: %s", " ".join(cmd))
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                self._logger.error(
                    "Parallel encoding failed with code %d: %s",
                    proc.returncode,
                    stderr.decode('utf-8')
                )
                return False
                
            return True
            
        except Exception as e:
            self._logger.error("Parallel encoding failed: %s", e)
            return False
            
    async def _concatenate_segments(self, segments_dir: Path, output_path: Path) -> bool:
        """Concatenate encoded segments into final output.
        
        Args:
            segments_dir: Directory containing encoded segments
            output_path: Path to final output file
            
        Returns:
            True if concatenation successful
        """
        try:
            # Create concat file
            concat_file = segments_dir / 'concat.txt'
            with open(concat_file, 'w') as f:
                for segment in sorted(segments_dir.glob('*.mkv')):
                    f.write(f"file '{segment.absolute()}'\n")
                    
            # Run ffmpeg concat
            cmd = [
                self.config.get('ffmpeg', 'ffmpeg'),
                '-hide_banner',
                '-loglevel', 'error',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',
                str(output_path)
            ]
            
            self._logger.info(f"Concatenating segments: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                self._logger.error(f"Concatenation failed: {stderr.decode()}")
                return False
                
            return True
            
        except Exception as e:
            self._logger.error(f"Concatenation failed: {e}")
            return False
