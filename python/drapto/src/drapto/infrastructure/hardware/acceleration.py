"""Hardware acceleration detection and configuration."""

import logging
import platform
import subprocess
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ffmpeg
from pydantic import BaseModel


class HardwareAccel(Enum):
    """Supported hardware acceleration types."""
    NONE = auto()
    VIDEOTOOLBOX = auto()
    VAAPI = auto()


class HardwareConfig(BaseModel):
    """Hardware acceleration configuration."""
    enable_hw_accel: bool = True
    force_software: bool = False
    vaapi_device: Optional[str] = "/dev/dri/renderD128"


class HardwareManager:
    """Manages hardware acceleration detection and configuration.
    
    This class handles detection and configuration of hardware acceleration
    features. Currently supports:
    - VideoToolbox on macOS Apple Silicon (arm64/aarch64)
    - VAAPI on Linux with supported GPUs
    
    The detection results are cached to avoid repeated system calls.
    """
    
    def __init__(self, ffmpeg_path: Optional[Path] = None):
        """Initialize hardware manager.
        
        Args:
            ffmpeg_path: Optional path to ffmpeg binary. If not provided,
                will search in system PATH.
                
        Raises:
            FileNotFoundError: If ffmpeg binary cannot be found
        """
        self._logger = logging.getLogger(__name__)
        self._ffmpeg_path = ffmpeg_path or Path("ffmpeg")
        self._detected_accel: Optional[HardwareAccel] = None
        self._config = HardwareConfig()
        
        # Validate ffmpeg path
        if not self._is_in_path(str(self._ffmpeg_path)):
            raise FileNotFoundError(f"FFmpeg not found: {self._ffmpeg_path}")

    def detect_acceleration(self) -> HardwareAccel:
        """Detect available hardware acceleration.
        
        This method checks for supported hardware acceleration features:
        - On macOS Apple Silicon: Checks for VideoToolbox support
        - On Linux: Checks for VAAPI support
        
        The detection result is cached after the first call.
        
        Returns:
            Detected hardware acceleration type
            
        Raises:
            subprocess.SubprocessError: If ffmpeg command fails
        """
        # Return cached result if available
        if self._detected_accel is not None:
            self._logger.debug("Using cached hardware acceleration: %s", 
                           self._detected_accel.name)
            return self._detected_accel
        
        # Check if hardware acceleration is disabled
        if not self._config.enable_hw_accel or self._config.force_software:
            self._logger.info("Hardware acceleration disabled by configuration")
            self._detected_accel = HardwareAccel.NONE
            return self._detected_accel
        
        # Check platform-specific hardware acceleration
        system = platform.system()
        machine = platform.machine()
        
        if system == "Darwin" and machine in ("arm64", "aarch64"):
            if self._check_videotoolbox():
                self._detected_accel = HardwareAccel.VIDEOTOOLBOX
                return self._detected_accel
                
        elif system == "Linux":
            if self._check_vaapi():
                self._detected_accel = HardwareAccel.VAAPI
                return self._detected_accel
        
        # No supported hardware acceleration found
        self._logger.info("No supported hardware acceleration found")
        self._detected_accel = HardwareAccel.NONE
        return self._detected_accel

    def get_ffmpeg_options(self) -> List[str]:
        """Get FFmpeg options for detected hardware acceleration.
        
        Returns:
            List of FFmpeg command line options
        """
        accel = self.detect_acceleration()
        
        if accel == HardwareAccel.VIDEOTOOLBOX:
            return ["-hwaccel", "videotoolbox"]
        elif accel == HardwareAccel.VAAPI:
            return [
                "-hwaccel", "vaapi",
                "-hwaccel_device", self._config.vaapi_device
            ]
        return []

    def _check_videotoolbox(self) -> bool:
        """Check for VideoToolbox support.
        
        Returns:
            True if VideoToolbox is supported and working
        """
        try:
            # Check if VideoToolbox is available
            result = subprocess.run(
                [str(self._ffmpeg_path), "-hide_banner", "-hwaccels"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            if "videotoolbox" not in result.stdout:
                self._logger.info("VideoToolbox not available")
                return False
                
            # Validate decoder works
            self._logger.debug("Testing VideoToolbox decoder")
            return self._validate_decoder("videotoolbox")
            
        except subprocess.SubprocessError as e:
            self._logger.warning("VideoToolbox check failed: %s", str(e))
            return False

    def _check_vaapi(self) -> bool:
        """Check for VAAPI support.
        
        Returns:
            True if VAAPI is supported and working
        """
        try:
            # Check if VAAPI device exists
            if not Path(self._config.vaapi_device).exists():
                self._logger.info("VAAPI device not found: %s", 
                              self._config.vaapi_device)
                return False
                
            # Check if VAAPI is available in FFmpeg
            result = subprocess.run(
                [str(self._ffmpeg_path), "-hide_banner", "-hwaccels"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            if "vaapi" not in result.stdout:
                self._logger.info("VAAPI not available in FFmpeg")
                return False
                
            # Check vainfo
            result = subprocess.run(
                ["vainfo"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            if "VAEntrypointVLD" not in result.stdout:
                self._logger.info("VAAPI decoder not supported")
                return False
                
            # Validate decoder works
            self._logger.debug("Testing VAAPI decoder")
            return self._validate_decoder(
                "vaapi",
                "-hwaccel_device", self._config.vaapi_device
            )
            
        except subprocess.SubprocessError as e:
            self._logger.warning("VAAPI check failed: %s", str(e))
            return False
        except FileNotFoundError:
            self._logger.warning("vainfo not found")
            return False

    def _validate_decoder(self, hwaccel: str, *options: str) -> bool:
        """Test if hardware decoder works.
        
        Args:
            hwaccel: Hardware acceleration type (e.g. videotoolbox, vaapi)
            options: Additional FFmpeg options
            
        Returns:
            True if decoder works
        """
        try:
            # Generate a test pattern and try to decode it
            cmd = [
                str(self._ffmpeg_path),
                "-f", "lavfi",
                "-i", "testsrc=duration=1:size=1280x720:rate=30",
                "-c:v", "libx264",
                "-f", "mp4",
                "-y",
                "-",  # Output to pipe
                "|",  # Pipe to next command
                str(self._ffmpeg_path),
                "-hwaccel", hwaccel,
                *options,
                "-i", "pipe:",  # Read from pipe
                "-f", "null",
                "-"
            ]
            
            # Run as shell command to support piping
            subprocess.run(
                " ".join(cmd),
                shell=True,
                capture_output=True,
                check=True,
                timeout=10
            )
            
            self._logger.info("Validated hardware decoder: %s", hwaccel)
            return True
            
        except subprocess.SubprocessError as e:
            self._logger.warning("Hardware decoder validation failed: %s", str(e))
            return False

    def _is_in_path(self, cmd: str) -> bool:
        """Check if a command is available in system PATH.
        
        Args:
            cmd: Command to check
            
        Returns:
            True if command is in PATH
        """
        try:
            subprocess.run([cmd, "-version"], capture_output=True, check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _get_platform_info(self) -> Dict[str, str]:
        """Get platform information.
        
        Returns:
            Dictionary with platform information
        """
        return {
            'platform_system': platform.system(),
            'platform_machine': platform.machine(),
            'platform_processor': platform.processor(),
            'platform_release': platform.release()
        }
