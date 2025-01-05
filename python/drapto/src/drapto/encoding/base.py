"""Base classes and interfaces for video encoding."""

import os
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, Protocol, List, Tuple
from pydantic import BaseModel, ConfigDict

from drapto.monitoring import ResourceMonitor

logger = logging.getLogger(__name__)

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
    
    async def encode_content(self, context: EncodingContext) -> bool:
        """Encode content according to context."""
        ...

class BaseEncoder:
    """Base class for video encoders."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize encoder with config."""
        self.config = config
        self._logger = logging.getLogger(self.__class__.__name__)
        
        # Initialize resource monitor with config
        self._monitor = ResourceMonitor(config)
    
    async def encode_content(self, context: EncodingContext) -> bool:
        """Encode content according to context."""
        raise NotImplementedError("Subclasses must implement encode_content")
    
    async def _validate_input(self, context: EncodingContext) -> bool:
        """Validate input file exists and is readable."""
        try:
            # Get input file size for disk space check
            input_size = os.path.getsize(context.input_path) if os.path.exists(context.input_path) else None
            
            # Check system resources first
            if not self._monitor.check_resources(context.input_path.parent, input_size):
                return False
                
            if not os.path.exists(context.input_path):
                self._logger.error("Input file does not exist")
                return False
            if not os.access(context.input_path, os.R_OK):
                self._logger.error("Input file is not readable")
                return False
                
            # Check dependencies
            if not self._check_dependencies():
                return False
                
            return True
        except Exception as e:
            self._logger.error(f"Input validation failed: {str(e)}")
            return False
    
    async def _validate_output(self, context: EncodingContext) -> bool:
        """Validate output file exists and is valid."""
        try:
            # Get input file size for disk space check
            input_size = os.path.getsize(context.input_path) if os.path.exists(context.input_path) else None
            
            # Check system resources first
            if not self._monitor.check_resources(context.output_path.parent, input_size):
                return False
                
            if not os.path.exists(context.output_path):
                self._logger.error("Output file does not exist")
                return False
            if os.path.getsize(context.output_path) == 0:
                self._logger.error("Output file is empty")
                return False
                
            # Check output streams and duration
            if not await self._validate_output_streams(context):
                return False
                
            return True
        except Exception as e:
            self._logger.error(f"Output validation failed: {str(e)}")
            return False
    
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        try:
            # Check ffmpeg and ffprobe
            ffmpeg = self.config.get('ffmpeg', 'ffmpeg')
            ffprobe = self.config.get('ffprobe', 'ffprobe')
            
            if not (shutil.which(ffmpeg) and shutil.which(ffprobe)):
                self._logger.error("ffmpeg and/or ffprobe not found")
                return False
            
            # Check mediainfo
            if not shutil.which('mediainfo'):
                self._logger.error("mediainfo not found")
                return False
            
            # Check bc (basic calculator)
            if not shutil.which('bc'):
                self._logger.error("bc not found")
                return False
            
            # Check ab-av1 if chunked encoding is enabled
            if self.config.get('enable_chunked_encoding', False):
                if not shutil.which('ab-av1'):
                    self._logger.error("ab-av1 not found (required for chunked encoding)")
                    return False
            
            return True
        except Exception as e:
            self._logger.error(f"Dependency check failed: {str(e)}")
            return False
    
    async def _validate_output_streams(self, context: EncodingContext) -> bool:
        """Validate output file streams and duration."""
        try:
            ffprobe = self.config.get('ffprobe', 'ffprobe')
            
            # Check video stream
            video_stream = await self._get_video_codec(ffprobe, context.output_path)
            if video_stream != 'av1':
                self._logger.error("No AV1 video stream found in output")
                return False
            
            # Check audio streams
            audio_streams = await self._get_audio_codecs(ffprobe, context.output_path)
            if not any(codec == 'opus' for codec in audio_streams):
                self._logger.error("No Opus audio streams found in output")
                return False
            
            # Compare durations
            input_duration = await self._get_duration(ffprobe, context.input_path)
            output_duration = await self._get_duration(ffprobe, context.output_path)
            
            if input_duration is None or output_duration is None:
                self._logger.error("Could not determine file durations")
                return False
            
            # Allow 1 second difference
            if abs(input_duration - output_duration) > 1:
                self._logger.error(
                    f"Output duration ({output_duration:.2f}s) differs significantly "
                    f"from input ({input_duration:.2f}s)"
                )
                return False
            
            return True
        except Exception as e:
            self._logger.error(f"Stream validation failed: {str(e)}")
            return False
    
    async def _get_video_codec(self, ffprobe: str, path: Path) -> Optional[str]:
        """Get video codec from file."""
        cmd = [
            ffprobe, '-v', 'error',
            '-select_streams', 'v',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(path)
        ]
        try:
            result = await self._run_command(cmd)
            return result.strip() if result else None
        except Exception:
            return None
    
    async def _get_audio_codecs(self, ffprobe: str, path: Path) -> List[str]:
        """Get list of audio codecs from file."""
        cmd = [
            ffprobe, '-v', 'error',
            '-select_streams', 'a',
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(path)
        ]
        try:
            result = await self._run_command(cmd)
            return [line.strip() for line in result.split('\n') if line.strip()]
        except Exception:
            return []
    
    async def _get_duration(self, ffprobe: str, path: Path) -> Optional[float]:
        """Get duration of file in seconds."""
        cmd = [
            ffprobe, '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(path)
        ]
        try:
            result = await self._run_command(cmd)
            return float(result.strip()) if result else None
        except (ValueError, TypeError):
            return None
    
    async def _run_command(self, cmd: List[str]) -> Optional[str]:
        """Run command and return output."""
        try:
            result = await subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            self._logger.error(f"Command failed: {e.stderr}")
            return None
            
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
