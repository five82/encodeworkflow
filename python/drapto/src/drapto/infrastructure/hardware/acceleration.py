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

        # Get platform info
        platform_info = self._get_platform_info()
        system = platform_info.get("system", "").lower()
        machine = platform_info.get("machine", "").lower()

        try:
            # Check for VideoToolbox on macOS Apple Silicon
            if system == "darwin" and machine in ["arm64", "aarch64"]:
                if self._check_videotoolbox():
                    self._detected_accel = HardwareAccel.VIDEOTOOLBOX
                    return self._detected_accel

            # Check for VAAPI on Linux
            elif system == "linux":
                if self._check_vaapi():
                    self._detected_accel = HardwareAccel.VAAPI
                    return self._detected_accel

        except Exception as e:
            self._logger.warning("Hardware acceleration detection failed: %s", str(e))

        # Fallback to software encoding
        self._logger.info("No supported hardware acceleration found, using software encoding")
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
            device = self._config.vaapi_device
            return ["-hwaccel", "vaapi", "-hwaccel_device", device]
        
        return []  # No hardware acceleration options

    def _check_videotoolbox(self) -> bool:
        """Check for VideoToolbox support.
        
        Returns:
            True if VideoToolbox is supported
        """
        try:
            result = subprocess.run(
                [str(self._ffmpeg_path), "-hide_banner", "-hwaccels"],
                capture_output=True,
                text=True,
                check=True
            )
            if "videotoolbox" in result.stdout:
                self._logger.info("Found VideoToolbox hardware acceleration")
                return True
        except subprocess.SubprocessError as e:
            self._logger.warning("VideoToolbox check failed: %s", str(e))
        return False

    def _check_vaapi(self) -> bool:
        """Check for VAAPI support.
        
        Returns:
            True if VAAPI is supported
        """
        # Check if VAAPI device exists
        device = Path(self._config.vaapi_device)
        if not device.exists():
            self._logger.warning("VAAPI device not found: %s", device)
            return False

        try:
            # Check if FFmpeg supports VAAPI
            result = subprocess.run(
                [str(self._ffmpeg_path), "-hide_banner", "-hwaccels"],
                capture_output=True,
                text=True,
                check=True
            )
            if "vaapi" not in result.stdout:
                self._logger.warning("FFmpeg does not support VAAPI")
                return False

            # Validate VAAPI device
            result = subprocess.run(
                ["vainfo", "--display", "drm", "--device", str(device)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and "VAEntrypointVLD" in result.stdout:
                self._logger.info("Found VAAPI hardware acceleration")
                return True
            else:
                self._logger.warning("VAAPI device validation failed")
                return False

        except FileNotFoundError:
            self._logger.warning("vainfo not found, cannot validate VAAPI device")
        except subprocess.SubprocessError as e:
            self._logger.warning("VAAPI check failed: %s", str(e))
        return False

    def _get_platform_info(self) -> Dict[str, str]:
        """Get platform information.
        
        Returns:
            Dictionary with platform information
        """
        return {
            "system": platform.system(),
            "machine": platform.machine(),
            "version": platform.version()
        }

    def _is_in_path(self, cmd: str) -> bool:
        """Check if a command is available in system PATH.
        
        Args:
            cmd: Command to check
            
        Returns:
            True if command is in PATH
        """
        try:
            subprocess.run([cmd, "-version"], 
                         capture_output=True, 
                         check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
