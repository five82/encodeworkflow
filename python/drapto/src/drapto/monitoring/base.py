"""Base classes and interfaces for resource monitoring."""

import os
import psutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SystemResources:
    """System resource snapshot."""
    cpu_percent: float
    memory_percent: float
    disk_free_bytes: int
    disk_total_bytes: int
    
    @property
    def disk_free_gb(self) -> float:
        """Get free disk space in GB."""
        return self.disk_free_bytes / (1024 * 1024 * 1024)
    
    @property
    def disk_total_gb(self) -> float:
        """Get total disk space in GB."""
        return self.disk_total_bytes / (1024 * 1024 * 1024)
    
    @property
    def disk_percent(self) -> float:
        """Get disk usage percentage."""
        return (1 - (self.disk_free_bytes / self.disk_total_bytes)) * 100

class ResourceMonitor:
    """Monitor system resources during encoding."""
    
    def __init__(self, min_disk_gb: float = 10.0, max_cpu_percent: float = 90.0, max_memory_percent: float = 90.0):
        """Initialize resource monitor.
        
        Args:
            min_disk_gb: Minimum required free disk space in GB
            max_cpu_percent: Maximum allowed CPU usage percentage
            max_memory_percent: Maximum allowed memory usage percentage
        """
        self._min_disk_bytes = min_disk_gb * 1024 * 1024 * 1024
        self._max_cpu_percent = max_cpu_percent
        self._max_memory_percent = max_memory_percent
        self._logger = logging.getLogger(__name__)
    
    def get_resources(self, path: Optional[Path] = None) -> SystemResources:
        """Get current system resource usage.
        
        Args:
            path: Optional path to check disk space for. If not provided,
                 uses the current working directory.
                 
        Returns:
            SystemResources object with current usage
        """
        path = path or Path.cwd()
        
        # Get disk usage for path
        disk_usage = psutil.disk_usage(str(path))
        
        # Get CPU and memory usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        return SystemResources(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_free_bytes=disk_usage.free,
            disk_total_bytes=disk_usage.total
        )
    
    def check_resources(self, path: Optional[Path] = None) -> bool:
        """Check if system resources are within acceptable limits.
        
        Args:
            path: Optional path to check disk space for
            
        Returns:
            True if resources are available, False otherwise
        """
        try:
            resources = self.get_resources(path)
            
            if resources.disk_free_bytes < self._min_disk_bytes:
                self._logger.error(
                    f"Insufficient disk space. Required: {self._min_disk_bytes / (1024**3):.1f}GB, "
                    f"Available: {resources.disk_free_gb:.1f}GB"
                )
                return False
                
            if resources.cpu_percent > self._max_cpu_percent:
                self._logger.error(
                    f"CPU usage too high. Maximum: {self._max_cpu_percent}%, "
                    f"Current: {resources.cpu_percent:.1f}%"
                )
                return False
                
            if resources.memory_percent > self._max_memory_percent:
                self._logger.error(
                    f"Memory usage too high. Maximum: {self._max_memory_percent}%, "
                    f"Current: {resources.memory_percent:.1f}%"
                )
                return False
                
            return True
            
        except Exception as e:
            self._logger.error(f"Resource check failed: {str(e)}")
            return False
