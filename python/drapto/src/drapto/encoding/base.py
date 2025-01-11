"""Base classes for video encoding."""

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from ..utils.logging import get_logger
from ..utils.validation import validate_input_file
from .types import VideoStreamInfo, QualitySettings


@dataclass
class EncodingContext:
    """Context for encoding operations.
    
    Attributes:
        input_path: Path to input video file
        output_path: Path to output video file
        target_vmaf: Target VMAF score (0-100)
        preset: SVT-AV1 preset (0-13, slower = better quality)
        svt_params: Additional SVT-AV1 parameters
        crop_filter: Optional FFmpeg crop filter
        hw_accel: Optional hardware acceleration type
        temp_dir: Optional temporary directory for intermediate files
    """
    input_path: Path
    output_path: Path
    target_vmaf: float
    preset: int
    svt_params: str
    crop_filter: Optional[str] = None
    hw_accel: Optional[str] = None
    temp_dir: Optional[Path] = None

    def __post_init__(self):
        """Validate and convert paths."""
        if isinstance(self.input_path, str):
            self.input_path = Path(self.input_path)
        if isinstance(self.output_path, str):
            self.output_path = Path(self.output_path)
        if isinstance(self.temp_dir, str):
            self.temp_dir = Path(self.temp_dir)


class BaseEncoder:
    """Base class for video encoders.
    
    Attributes:
        logger: Logger instance
        config: Configuration dictionary
    """
    
    REQUIRED_DEPENDENCIES = ['ffmpeg', 'ffprobe', 'mediainfo']
    OPTIONAL_DEPENDENCIES = ['bc', 'ab-av1']
    MIN_DISK_SPACE = 10 * 1024 * 1024 * 1024  # 10GB
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize encoder.
        
        Args:
            config: Optional configuration dictionary
        """
        self.logger = get_logger(__name__)
        self.config = config or {}
        
    async def encode_content(self, context: EncodingContext) -> bool:
        """Encode video content.
        
        Args:
            context: Encoding context
            
        Returns:
            True if encoding succeeded, False otherwise
            
        Raises:
            FileNotFoundError: If input file does not exist
            ValueError: If input validation fails
            RuntimeError: If encoding fails
        """
        try:
            # Validate input file and resources
            if not await self._validate_input(context):
                return False
                
            # Check dependencies
            if not self._check_dependencies():
                return False
            
            # Analyze input stream
            stream_info = await self._analyze_stream(context)
            
            # Get quality settings
            quality_settings = await self._get_quality_settings(context, stream_info)
            
            # Build and run FFmpeg command
            success = await self._run_command(context, stream_info, quality_settings)
            if not success:
                raise RuntimeError("FFmpeg command failed")
            
            # Validate output
            if not await self._validate_output(context):
                raise RuntimeError("Output validation failed")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Encoding failed: {str(e)}")
            return False

    async def _validate_input(self, context: EncodingContext) -> bool:
        """Validate input file and resources.
        
        Args:
            context: Encoding context
            
        Returns:
            True if validation passed, False otherwise
        """
        try:
            # Check available resources first
            resources = self.get_resources(context.output_path.parent)
            
            # Check if disk space is too low (< 10GB)
            if resources['disk_free_gb'] < 10:
                self.logger.error(f"Insufficient disk space: {resources['disk_free_gb']:.2f} GB")
                return False
                
            # Check if disk is too full (>90%)
            if resources['disk_percent'] > 90:
                self.logger.error(f"Disk usage too high: {resources['disk_percent']:.1f}%")
                return False
                
            # Check if CPU is too busy (>80%)
            if resources['cpu_percent'] > 80:
                self.logger.error(f"CPU usage too high: {resources['cpu_percent']:.1f}%")
                return False
                
            # Check if memory is too full (>90%)
            if resources['memory_percent'] > 90:
                self.logger.error(f"Memory usage too high: {resources['memory_percent']:.1f}%")
                return False
            
            # Then check input file
            validate_input_file(context.input_path)
            return True
            
        except Exception as e:
            self.logger.error(f"Input validation failed: {str(e)}")
            return False
    
    def get_resources(self, path: Path) -> Dict[str, float]:
        """Get resource usage for a path.
        
        Args:
            path: Path to check resources for
            
        Returns:
            Dictionary with resource information
        """
        import psutil
        usage = shutil.disk_usage(path)
        return {
            'total_space': usage.total,
            'used_space': usage.used,
            'free_space': usage.free,
            'disk_percent': (usage.used / usage.total) * 100,
            'disk_free_gb': usage.free / (1024 * 1024 * 1024),  # Convert to GB
            'cpu_percent': psutil.cpu_percent(),
            'memory_percent': psutil.virtual_memory().percent
        }
    
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available.
        
        Returns:
            True if all required dependencies are available
        """
        try:
            # Check required dependencies
            for dep in self.REQUIRED_DEPENDENCIES:
                if not shutil.which(dep):
                    self.logger.error(f"Required dependency not found: {dep}")
                    return False
            
            # Check optional dependencies based on config
            if self.config.get('enable_chunked_encoding', True):
                for dep in self.OPTIONAL_DEPENDENCIES:
                    if not shutil.which(dep):
                        self.logger.warning(f"Optional dependency not found: {dep}")
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Dependency check failed: {str(e)}")
            return False
    
    async def _analyze_stream(self, context: EncodingContext) -> VideoStreamInfo:
        """Analyze input stream.
        
        Args:
            context: Encoding context
            
        Returns:
            Stream information
            
        Raises:
            RuntimeError: If stream analysis fails
        """
        raise NotImplementedError
    
    async def _get_quality_settings(
        self,
        context: EncodingContext,
        stream_info: VideoStreamInfo
    ) -> QualitySettings:
        """Get quality settings based on stream info.
        
        Args:
            context: Encoding context
            stream_info: Stream information
            
        Returns:
            Quality settings
            
        Raises:
            RuntimeError: If quality settings cannot be determined
        """
        raise NotImplementedError
    
    async def _run_command(
        self,
        context: EncodingContext,
        stream_info: VideoStreamInfo,
        quality_settings: QualitySettings
    ) -> bool:
        """Run FFmpeg command.
        
        Args:
            context: Encoding context
            stream_info: Stream information
            quality_settings: Quality settings
            
        Returns:
            True if command succeeded, False otherwise
        """
        raise NotImplementedError
    
    async def _validate_output(self, context: EncodingContext) -> bool:
        """Validate output file.
        
        Args:
            context: Encoding context
            
        Returns:
            True if validation passed, False otherwise
        """
        try:
            # Check if output file exists and has content
            if not context.output_path.exists() or context.output_path.stat().st_size == 0:
                self.logger.error("Output file missing or empty")
                return False
            
            # Get input video codec
            input_codec = await self._get_video_codec(context.input_path)
            output_codec = await self._get_video_codec(context.output_path)
            if input_codec != output_codec:
                self.logger.error(f"Video codec mismatch: {input_codec} != {output_codec}")
                return False
            
            # Get audio codecs
            input_codecs = await self._get_audio_codecs(context.input_path)
            output_codecs = await self._get_audio_codecs(context.output_path)
            if input_codecs != output_codecs:
                self.logger.error(f"Audio codec mismatch: {input_codecs} != {output_codecs}")
                return False
            
            # Get durations
            input_duration = await self._get_duration(context.input_path)
            output_duration = await self._get_duration(context.output_path)
            
            # Allow small duration difference (0.5%)
            duration_diff = abs(input_duration - output_duration)
            if duration_diff > (input_duration * 0.005):
                self.logger.error(f"Duration mismatch: {input_duration} != {output_duration}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Output validation failed: {str(e)}")
            return False

    async def _get_video_codec(self, path: Path) -> str:
        """Get video codec from file.
        
        Args:
            path: Path to file
            
        Returns:
            Video codec name
            
        Raises:
            RuntimeError: If codec cannot be determined
        """
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                  '-show_entries', 'stream=codec_name', '-of', 'default=noprint_wrappers=1:nokey=1',
                  str(path)]
            success, output = await self._run_command(cmd)
            if not success:
                raise RuntimeError("ffprobe command failed")
            return output.strip()
        except Exception as e:
            raise RuntimeError(f"Failed to get video codec: {str(e)}")

    async def _get_audio_codecs(self, path: Path) -> List[str]:
        """Get audio codecs from file.
        
        Args:
            path: Path to file
            
        Returns:
            List of audio codec names
            
        Raises:
            RuntimeError: If codecs cannot be determined
        """
        try:
            cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a', 
                  '-show_entries', 'stream=codec_name', '-of', 'default=noprint_wrappers=1:nokey=1',
                  str(path)]
            success, output = await self._run_command(cmd)
            if not success:
                raise RuntimeError("ffprobe command failed")
            return output.strip().split('\n')
        except Exception as e:
            raise RuntimeError(f"Failed to get audio codecs: {str(e)}")

    async def _get_duration(self, path: Path) -> float:
        """Get duration from file.
        
        Args:
            path: Path to file
            
        Returns:
            Duration in seconds
            
        Raises:
            RuntimeError: If duration cannot be determined
        """
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                  '-of', 'default=noprint_wrappers=1:nokey=1', str(path)]
            success, output = await self._run_command(cmd)
            if not success:
                raise RuntimeError("ffprobe command failed")
            return float(output.strip())
        except Exception as e:
            raise RuntimeError(f"Failed to get duration: {str(e)}")
