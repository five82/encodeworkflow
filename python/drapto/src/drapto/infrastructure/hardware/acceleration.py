"""Hardware acceleration support for encoding.

This module provides functionality to detect and configure hardware acceleration
options for video encoding. Currently supports:
- VideoToolbox on macOS Apple Silicon (arm64/aarch64)
"""

import logging
import platform
import subprocess
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from drapto.core.base import BaseEncoder


class HardwareAccel(Enum):
    """Supported hardware acceleration types."""
    NONE = auto()
    VIDEOTOOLBOX = auto()


@dataclass
class HardwareConfig:
    """Hardware acceleration configuration.
    
    Attributes:
        accel_type: Type of hardware acceleration
        ffmpeg_opts: FFmpeg options for hardware acceleration
        fallback_opts: FFmpeg options for software fallback
        platform_info: Dictionary containing platform information
    """
    accel_type: HardwareAccel
    ffmpeg_opts: List[str]
    fallback_opts: List[str]
    platform_info: Dict[str, str]


class HardwareManager:
    """Manages hardware acceleration detection and configuration.
    
    This class handles detection and configuration of hardware acceleration
    features. Currently supports:
    - VideoToolbox on macOS Apple Silicon (arm64/aarch64)
    
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
        
        # Validate ffmpeg path
        if not self._ffmpeg_path.is_file() and not self._is_in_path(str(self._ffmpeg_path)):
            raise FileNotFoundError(f"FFmpeg binary not found: {self._ffmpeg_path}")
            
    def _is_in_path(self, cmd: str) -> bool:
        """Check if a command is available in system PATH.
        
        Args:
            cmd: Command to check
            
        Returns:
            True if command is in PATH
        """
        try:
            subprocess.run([cmd, "-version"], 
                         stdout=subprocess.DEVNULL, 
                         stderr=subprocess.DEVNULL,
                         check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
            
    @classmethod
    def _get_platform_info(cls) -> Dict[str, str]:
        """Get platform information.
        
        Returns:
            Dictionary containing platform information
        """
        return {
            'system': platform.system().lower(),
            'machine': platform.machine().lower(),
            'processor': platform.processor(),
            'release': platform.release()
        }
        
    @classmethod
    def _is_apple_silicon(cls, platform_info: Dict[str, str]) -> bool:
        """Check if running on Apple Silicon.
        
        Args:
            platform_info: Dictionary containing platform information
        
        Returns:
            True if running on Apple Silicon
        """
        return (platform_info['system'] == 'darwin' and 
                platform_info['machine'] in ['arm64', 'aarch64'])
                
    def detect_acceleration(self) -> HardwareAccel:
        """Detect available hardware acceleration.
        
        This method checks for supported hardware acceleration features:
        - On macOS Apple Silicon: Checks for VideoToolbox support
        
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
            
        # Only check for VideoToolbox on Apple Silicon
        platform_info = self._get_platform_info()
        if self._is_apple_silicon(platform_info):
            self._logger.info("Detected Apple Silicon platform")
            try:
                output = subprocess.check_output(
                    [str(self._ffmpeg_path), "-hide_banner", "-hwaccels"],
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5  # Add timeout
                )
                
                if "videotoolbox" in output.lower():
                    self._logger.info("Found VideoToolbox hardware acceleration")
                    self._detected_accel = HardwareAccel.VIDEOTOOLBOX
                    return self._detected_accel
                    
                self._logger.warning("VideoToolbox not found in available accelerators")
                    
            except subprocess.TimeoutExpired:
                self._logger.error("Timeout while detecting hardware acceleration")
            except subprocess.CalledProcessError as e:
                self._logger.error("Failed to detect hardware acceleration: %s", e)
                if e.stderr:
                    self._logger.debug("FFmpeg error output: %s", e.stderr)
            except Exception as e:
                self._logger.error("Unexpected error during hardware detection: %s", e)
        else:
            self._logger.info("Platform does not support hardware acceleration: %s %s", 
                            platform_info['system'],
                            platform_info['machine'])
                
        self._detected_accel = HardwareAccel.NONE
        return self._detected_accel
        
    def get_config(self) -> HardwareConfig:
        """Get hardware acceleration configuration.
        
        Returns:
            Hardware acceleration configuration with platform info
        """
        accel_type = self.detect_acceleration()
        platform_info = self._get_platform_info()
        
        if accel_type == HardwareAccel.VIDEOTOOLBOX:
            return HardwareConfig(
                accel_type=accel_type,
                ffmpeg_opts=["-hwaccel", "videotoolbox"],
                fallback_opts=[],  # No special options needed for software fallback
                platform_info=platform_info
            )
            
        return HardwareConfig(
            accel_type=HardwareAccel.NONE,
            ffmpeg_opts=[],  # No hardware acceleration options
            fallback_opts=[],  # No fallback needed
            platform_info=platform_info
        )
        
    def monitor_performance(self, encoder: BaseEncoder) -> Dict[str, float]:
        """Monitor hardware acceleration performance.
        
        Args:
            encoder: Encoder instance to monitor
            
        Returns:
            Dictionary with performance metrics and hardware info
        """
        # Get current resource usage
        resources = encoder.get_resources()
        platform_info = self._get_platform_info()
        
        metrics = {
            'cpu_percent': resources['cpu_percent'],
            'memory_percent': resources['memory_percent'],
            'hw_accel_type': self._detected_accel.name if self._detected_accel else 'NONE'
        }
        
        # Add platform info if using hardware acceleration
        if self._detected_accel != HardwareAccel.NONE:
            metrics.update({
                'platform_' + k: v 
                for k, v in platform_info.items()
            })
            
        return metrics
