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

        Returns:
            HardwareAccel: Detected hardware acceleration type
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

        try:
            # Get supported hwaccels
            result = subprocess.run(
                [str(self._ffmpeg_path), "-hwaccels"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            hwaccels = result.stdout.strip().split("\n")

            # Check for VideoToolbox on macOS
            if (platform.system() == "Darwin" and
                platform.machine() == "arm64" and
                "videotoolbox" in hwaccels):
                if self._validate_decoder("videotoolbox"):
                    self._detected_accel = HardwareAccel.VIDEOTOOLBOX
                    return self._detected_accel

            # Check for VAAPI on Linux
            if (platform.system() == "Linux" and
                "vaapi" in hwaccels and
                Path("/dev/dri/renderD128").exists()):
                if self._validate_decoder("vaapi"):
                    self._detected_accel = HardwareAccel.VAAPI
                    return self._detected_accel

        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass

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

    def _validate_decoder(self, decoder: str) -> bool:
        """Test if hardware decoder works by decoding a test pattern.
        
        Args:
            decoder: Name of hardware decoder to test
            
        Returns:
            bool: True if decoder works, False otherwise
        """
        try:
            # Generate test pattern and pipe to decoder
            cmd = [
                str(self._ffmpeg_path),
                "-f", "lavfi",
                "-i", "testsrc=duration=1:size=64x64:rate=1",
                "-c:v", "rawvideo",
                "-f", "null",
                "-"
            ]
            
            if decoder == "videotoolbox":
                cmd[1:1] = ["-hwaccel", "videotoolbox"]
            elif decoder == "vaapi":
                cmd[1:1] = [
                    "-hwaccel", "vaapi",
                    "-hwaccel_device", "/dev/dri/renderD128"
                ]
                
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                timeout=5
            )
            return True
            
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
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
