"""Hardware acceleration support for encoding.

This module provides functionality to detect and configure hardware acceleration
options for video encoding. Currently supports:
- VideoToolbox on macOS
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
    """
    accel_type: HardwareAccel
    ffmpeg_opts: List[str]
    fallback_opts: List[str]


class HardwareManager:
    """Manages hardware acceleration detection and configuration."""
    
    def __init__(self, ffmpeg_path: Optional[Path] = None):
        """Initialize hardware manager.
        
        Args:
            ffmpeg_path: Optional path to ffmpeg binary. If not provided,
                will search in system PATH.
        """
        self._logger = logging.getLogger(__name__)
        self._ffmpeg_path = ffmpeg_path or Path("ffmpeg")
        self._detected_accel: Optional[HardwareAccel] = None
        
    def detect_acceleration(self) -> HardwareAccel:
        """Detect available hardware acceleration.
        
        Returns:
            Detected hardware acceleration type
        """
        if self._detected_accel is not None:
            return self._detected_accel
            
        # Currently only support VideoToolbox on macOS
        if platform.system() == "Darwin":
            try:
                output = subprocess.check_output(
                    [str(self._ffmpeg_path), "-hide_banner", "-hwaccels"],
                    stderr=subprocess.PIPE,
                    text=True
                )
                if "videotoolbox" in output.lower():
                    self._logger.info("Found VideoToolbox hardware acceleration")
                    self._detected_accel = HardwareAccel.VIDEOTOOLBOX
                    return self._detected_accel
                    
            except subprocess.CalledProcessError as e:
                self._logger.warning("Failed to detect hardware acceleration: %s", e)
                
        self._logger.info("No supported hardware acceleration found")
        self._detected_accel = HardwareAccel.NONE
        return self._detected_accel
        
    def get_config(self) -> HardwareConfig:
        """Get hardware acceleration configuration.
        
        Returns:
            Hardware acceleration configuration
        """
        accel_type = self.detect_acceleration()
        
        if accel_type == HardwareAccel.VIDEOTOOLBOX:
            return HardwareConfig(
                accel_type=accel_type,
                ffmpeg_opts=["-hwaccel", "videotoolbox"],
                fallback_opts=[]  # No special options needed for software fallback
            )
            
        return HardwareConfig(
            accel_type=HardwareAccel.NONE,
            ffmpeg_opts=[],  # No hardware acceleration options
            fallback_opts=[]  # No fallback needed
        )
        
    def monitor_performance(self, encoder: BaseEncoder) -> Dict[str, float]:
        """Monitor hardware acceleration performance.
        
        Args:
            encoder: Encoder instance to monitor
            
        Returns:
            Dictionary with performance metrics
        """
        # Get current resource usage
        resources = encoder.get_resources()
        
        return {
            'cpu_percent': resources['cpu_percent'],
            'memory_percent': resources['memory_percent'],
            'hw_accel_type': self._detected_accel.name
        }
