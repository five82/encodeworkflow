"""Base classes and interfaces for the Drapto encoding system.

This module provides the core abstractions and base classes used throughout Drapto:
- EncodingContext: Configuration and context for encoding operations
- EncodingPath: Protocol defining the interface for encoding paths
- BaseEncoder: Abstract base class implementing common encoder functionality
"""

import os
import shutil
import logging
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Protocol, List, Tuple
from pydantic import BaseModel, ConfigDict

from drapto.infrastructure.monitoring.resources import ResourceMonitor


class EncodingContext(BaseModel):
    """Context for encoding operation."""
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_default=True,
        str_strip_whitespace=True,
        validate_assignment=True
    )
    
    input_path: Path
    output_path: Path
    target_vmaf: float
    preset: int
    svt_params: str
    crop_filter: Optional[str] = None


class EncodingPath(Protocol):
    """Protocol for encoding path implementations."""
    
    async def encode_content(self, context: EncodingContext) -> None:
        """Encode content according to context."""
        ...


class BaseEncoder:
    """Base class for video encoders.
    
    Provides common functionality for:
    - Resource monitoring
    - Input/output validation
    - Dependency checking
    - Command execution
    - FFmpeg integration
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize encoder with config."""
        self.config = config
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize resource monitor with config
        self._monitor = ResourceMonitor(config)
        
    async def encode_content(self, context: EncodingContext) -> None:
        """Encode content according to context.
        
        This is the main entry point for encoding. Subclasses should override
        this method to implement their specific encoding logic.
        
        Args:
            context: The encoding context containing input/output paths and parameters
            
        Raises:
            ValueError: If input validation fails
            RuntimeError: If encoding fails
        """
        if not await self._validate_input(context):
            raise ValueError("Input validation failed")
        if not self._check_dependencies():
            raise RuntimeError("Missing required dependencies")
        
    async def _validate_input(self, context: EncodingContext) -> bool:
        """Validate input file exists and is readable.
        
        Args:
            context: The encoding context
            
        Returns:
            True if validation passes, False if validation fails
        """
        if not context.input_path.exists():
            self._logger.error(f"Input file does not exist: {context.input_path}")
            return False
            
        if not os.access(context.input_path, os.R_OK):
            self._logger.error(f"Input file is not readable: {context.input_path}")
            return False
            
        # Check if we have enough resources
        resources = self._monitor.get_resources(context.input_path)
        if resources.disk_free_gb < 10:  # Require at least 10GB free
            self._logger.error("Insufficient disk space: %.1f GB free", resources.disk_free_gb)
            return False
            
        return True

    async def _validate_output(self, context: EncodingContext) -> bool:
        """Validate output file exists and is valid.
        
        Args:
            context: The encoding context
            
        Returns:
            True if validation passes, False otherwise
        """
        if not context.output_path.exists():
            self._logger.error(f"Output file not found: {context.output_path}")
            return False
            
        if not os.access(context.output_path, os.R_OK):
            self._logger.error(f"Output file is not readable: {context.output_path}")
            return False
            
        return await self._validate_output_streams(context)
            
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available.
        
        Returns:
            True if all dependencies are available, False otherwise
        """
        required = ['ffmpeg', 'ffprobe', 'mediainfo', 'bc']
        if self.config.get('enable_chunked_encoding', True):
            required.append('ab-av1')
            
        for cmd in required:
            if not shutil.which(cmd):
                self._logger.error(f"Required dependency not found: {cmd}")
                return False
                
        return True
        
    async def _validate_output_streams(self, context: EncodingContext) -> bool:
        """Validate output file streams and duration.
        
        Args:
            context: The encoding context
            
        Returns:
            True if validation passes, False otherwise
        """
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            self._logger.error("ffprobe not found")
            return False
            
        try:
            # Get video codecs first
            input_video = await self._get_video_codec(ffprobe, context.input_path)
            if not input_video:
                self._logger.error("Input file has no video stream")
                return False
                
            output_video = await self._get_video_codec(ffprobe, context.output_path)
            if not output_video:
                self._logger.error("Output file has no video stream")
                return False
                
            if input_video != output_video:
                self._logger.error(
                    "Output video codec %s differs from input codec %s",
                    output_video, input_video
                )
                return False
                
            # Get audio codecs
            input_audio = await self._get_audio_codecs(ffprobe, context.input_path)
            output_audio = await self._get_audio_codecs(ffprobe, context.output_path)
            if len(input_audio) != len(output_audio):
                self._logger.error(
                    "Output has %d audio streams, expected %d",
                    len(output_audio), len(input_audio)
                )
                return False
                
            if input_audio != output_audio:
                self._logger.error(
                    "Output audio codecs %s differ from input codecs %s",
                    output_audio, input_audio
                )
                return False
                
            # Get durations last
            input_duration = await self._get_duration(ffprobe, context.input_path)
            output_duration = await self._get_duration(ffprobe, context.output_path)
            
            # Allow 1% difference in duration
            duration_diff = abs(input_duration - output_duration)
            if duration_diff > input_duration * 0.01:
                self._logger.error(
                    "Output duration %.2fs differs from input duration %.2fs by more than 1%%",
                    output_duration, input_duration
                )
                return False
                
            return True
            
        except ValueError as e:
            self._logger.error("Output validation failed: %s", e)
            return False
            
    async def _get_video_codec(self, ffprobe: str, path: Path) -> Optional[str]:
        """Get video codec from file.
        
        Args:
            ffprobe: Path to ffprobe binary
            path: Path to media file
            
        Returns:
            Video codec name or None if no video stream found
        """
        cmd = [
            str(ffprobe),  # Convert potential bool to str
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ]
        try:
            output = await self._run_command(cmd)
            return output.strip() if output else None
        except subprocess.CalledProcessError:
            return None
            
    async def _get_audio_codecs(self, ffprobe: str, path: Path) -> List[str]:
        """Get list of audio codecs from file.
        
        Args:
            ffprobe: Path to ffprobe binary
            path: Path to media file
            
        Returns:
            List of audio codec names
        """
        cmd = [
            str(ffprobe),  # Convert potential bool to str
            "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ]
        try:
            output = await self._run_command(cmd)
            return [line.strip() for line in output.splitlines() if line.strip()]
        except subprocess.CalledProcessError:
            return []
            
    async def _get_duration(self, ffprobe: str, path: Path) -> float:
        """Get duration of file in seconds.
        
        Args:
            ffprobe: Path to ffprobe binary
            path: Path to media file
            
        Returns:
            Duration in seconds
            
        Raises:
            ValueError: If duration cannot be determined
        """
        cmd = [
            str(ffprobe),  # Convert potential bool to str
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ]
        try:
            output = await self._run_command(cmd)
            if not output.strip():
                raise ValueError("Empty duration")
            return float(output.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            raise ValueError(f"Could not determine duration: {e}")
            
    async def _run_command(self, cmd: List[str]) -> str:
        """Run command and return output.
        
        Args:
            cmd: Command and arguments to run
            
        Returns:
            Command output as string
            
        Raises:
            subprocess.CalledProcessError: If command fails
        """
        self._logger.debug("Running command: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, stdout, stderr
            )
            
        return stdout.decode('utf-8')
        
    def get_resources(self, path: Optional[Path] = None) -> Dict[str, float]:
        """Get current resource usage.
        
        Args:
            path: Optional path to check disk space for
            
        Returns:
            Dictionary with current resource usage percentages
        """
        resources = self._monitor.get_resources(path)
        return {
            'cpu_percent': resources.cpu_percent,
            'memory_percent': resources.memory_percent,
            'disk_percent': resources.disk_percent,
            'disk_free_gb': resources.disk_free_gb
        }
