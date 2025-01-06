"""Resource monitoring utilities."""

import os
import psutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

from drapto.config import EncodingConfig


@dataclass
class SystemResources:
    """System resource information.
    
    Attributes:
        cpu_percent: CPU usage percentage
        memory_percent: Memory usage percentage
        disk_percent: Disk usage percentage
        disk_free_gb: Free disk space in GB
        io_counters: Disk I/O statistics
        network_counters: Network I/O statistics
        process_count: Number of encoding processes
    """
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    disk_free_gb: float
    io_counters: Optional[Dict[str, int]] = None
    network_counters: Optional[Dict[str, int]] = None
    process_count: int = 0


class ResourceMonitor:
    """Monitor system resources."""
    
    def __init__(self, config: Union[Dict[str, Any], EncodingConfig]):
        """Initialize monitor with config."""
        self.config = config
        self._logger = logging.getLogger(__name__)
        self._process_cache: Dict[int, psutil.Process] = {}
        
    def get_resources(self, path: Optional[Path] = None) -> SystemResources:
        """Get current resource usage.
        
        Args:
            path: Optional path to check disk space for
            
        Returns:
            Current system resource information
        """
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        # Get disk usage for path or current directory
        disk_path = path if path else Path.cwd()
        disk = psutil.disk_usage(disk_path)
        disk_free_gb = disk.free / (1024 * 1024 * 1024)  # Convert to GB
        disk_percent = disk.percent
        
        # Get I/O counters
        try:
            io = psutil.disk_io_counters()
            io_stats = {
                'read_bytes': io.read_bytes,
                'write_bytes': io.write_bytes,
                'read_count': io.read_count,
                'write_count': io.write_count
            } if io else None
        except Exception as e:
            self._logger.debug(f"Failed to get I/O counters: {e}")
            io_stats = None
            
        # Get network counters
        try:
            net = psutil.net_io_counters()
            net_stats = {
                'bytes_sent': net.bytes_sent,
                'bytes_recv': net.bytes_recv,
                'packets_sent': net.packets_sent,
                'packets_recv': net.packets_recv
            } if net else None
        except Exception as e:
            self._logger.debug(f"Failed to get network counters: {e}")
            net_stats = None
            
        # Count encoding processes
        process_count = self._count_encoding_processes()
        
        return SystemResources(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_percent=disk_percent,
            disk_free_gb=disk_free_gb,
            io_counters=io_stats,
            network_counters=net_stats,
            process_count=process_count
        )
        
    def _count_encoding_processes(self) -> int:
        """Count number of active encoding processes."""
        count = 0
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if any(x in proc.info['name'].lower() for x in ['ffmpeg', 'ab-av1']):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return count
        
    def cleanup_resources(self, work_dir: Path) -> None:
        """Clean up temporary resources.
        
        Args:
            work_dir: Working directory to clean
        """
        try:
            # Clean up any leftover temporary files
            for pattern in ['*.mkv', '*.mp4', '*.log', '*.txt']:
                for file in work_dir.glob(pattern):
                    if file.is_file():
                        try:
                            file.unlink()
                            self._logger.debug(f"Cleaned up: {file}")
                        except OSError as e:
                            self._logger.warning(f"Failed to clean up {file}: {e}")
                            
            # Clean up empty directories
            for dir_path in work_dir.glob('**/*'):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                        self._logger.debug(f"Cleaned up empty directory: {dir_path}")
                    except OSError as e:
                        self._logger.warning(f"Failed to clean up directory {dir_path}: {e}")
                        
        except Exception as e:
            self._logger.error(f"Cleanup failed: {e}")
            
    def optimize_resources(self) -> None:
        """Optimize system resources for encoding."""
        try:
            # Set process priority
            current_process = psutil.Process()
            if os.name != 'nt':  # Unix systems
                current_process.nice(10)  # Lower priority slightly
                
            # Adjust I/O priority if possible
            if hasattr(os, 'IOPRIO_CLASS_BE'):  # Linux
                try:
                    os.system(f'ionice -c 2 -n 7 -p {current_process.pid}')
                except Exception as e:
                    self._logger.debug(f"Failed to set I/O priority: {e}")
                    
            # Clean up process cache
            self._process_cache.clear()
            
        except Exception as e:
            self._logger.error(f"Resource optimization failed: {e}")
            
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

    def _get_config_value(self, key: str, default: Any) -> Any:
        """Get config value handling both dict and EncodingConfig."""
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        return getattr(self.config, key, default)
