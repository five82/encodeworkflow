"""Resource monitoring utilities."""

import os
import psutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

from drapto.config import EncodingConfig

logger = logging.getLogger(__name__)

@dataclass
class SystemResources:
    """System resource information."""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    disk_free_gb: float

class ResourceMonitor:
    """Monitor system resources."""
    
    def __init__(self, config: Union[Dict[str, Any], EncodingConfig]):
        """Initialize monitor with config."""
        self.config = config
        self._logger = logging.getLogger(__name__)
        
    def get_resources(self, path: Optional[Path] = None) -> SystemResources:
        """Get current resource usage."""
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        # Get disk usage for path or current directory
        disk_path = path if path else Path.cwd()
        disk = psutil.disk_usage(disk_path)
        disk_free_gb = disk.free / (1024 * 1024 * 1024)  # Convert to GB
        disk_percent = disk.percent
        
        return SystemResources(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk_percent,
            disk_free_gb=disk_free_gb
        )
    
    def _get_config_value(self, key: str, default: Any) -> Any:
        """Get config value handling both dict and EncodingConfig."""
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        return getattr(self.config, key, default)
    
    def check_resources(self, path: Optional[Path] = None, input_size: Optional[int] = None) -> bool:
        """Check if system has enough resources."""
        try:
            resources = self.get_resources(path)
            
            # Get config values
            min_disk_gb = self._get_config_value('min_disk_gb', 50.0)
            max_cpu_percent = self._get_config_value('max_cpu_percent', 80.0)
            max_memory_percent = self._get_config_value('max_memory_percent', 80.0)
            disk_buffer_factor = self._get_config_value('disk_buffer_factor', 1.5)
            enable_chunked_encoding = self._get_config_value('enable_chunked_encoding', False)
            segment_length = self._get_config_value('segment_length', 1)
            
            # Calculate required disk space
            required_gb = min_disk_gb
            if input_size:
                # For chunked encoding, we need space for:
                # 1. Input file copy (if not in work dir)
                # 2. Temporary chunks
                # 3. Encoded chunks
                # 4. Final output
                # Plus buffer factor for safety
                if enable_chunked_encoding:
                    chunk_space = input_size * (1 + 1/segment_length)
                    required_bytes = (input_size + chunk_space) * disk_buffer_factor
                    required_gb += required_bytes / (1024 * 1024 * 1024)
                else:
                    # For non-chunked, just input + output + buffer
                    required_bytes = input_size * 2 * disk_buffer_factor
                    required_gb += required_bytes / (1024 * 1024 * 1024)
            
            # Check resources
            if resources.disk_free_gb < required_gb:
                self._logger.error(
                    f"Not enough disk space. Required: {required_gb:.1f}GB, "
                    f"Available: {resources.disk_free_gb:.1f}GB"
                )
                return False
                
            if resources.cpu_percent > max_cpu_percent:
                self._logger.error(
                    f"CPU usage too high. Maximum: {max_cpu_percent}%, "
                    f"Current: {resources.cpu_percent:.1f}%"
                )
                return False
                
            if resources.memory_percent > max_memory_percent:
                self._logger.error(
                    f"Memory usage too high. Maximum: {max_memory_percent}%, "
                    f"Current: {resources.memory_percent:.1f}%"
                )
                return False
            
            return True
        except Exception as e:
            self._logger.error(f"Resource check failed: {str(e)}")
            return False
