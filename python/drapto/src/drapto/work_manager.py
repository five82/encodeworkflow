"""Work directory management for drapto."""

import atexit
import shutil
import signal
import os
from pathlib import Path
from typing import Dict, Set
from contextlib import contextmanager

from loguru import logger

from .path_manager import PathManager


class WorkDirectoryManager:
    """Manages work directories for processing tasks."""
    
    def __init__(self, config):
        """Initialize work directory manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self._active_dirs: Set[Path] = set()
        
        # Register cleanup handlers
        atexit.register(self.cleanup_all)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Set up process group to handle child processes
        os.setpgrp()
        
    def _signal_handler(self, signum, frame):
        """Handle interruption signals by cleaning up work directories."""
        logger.info(f"Received signal {signum}, cleaning up...")
        try:
            # Try to terminate any child processes in our process group
            if signum in (signal.SIGINT, signal.SIGTERM):
                os.killpg(os.getpgid(0), signum)
        except Exception as e:
            logger.error(f"Error terminating child processes: {e}")
            
        self.cleanup_all()
        # Re-raise the signal
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)
        
    @contextmanager
    def work_space(self, output_file: Path) -> Dict[str, Path]:
        """Context manager for work space creation and cleanup.
        
        Args:
            output_file: Output file path
            
        Yields:
            Dictionary of work directory paths
        """
        # Create work directories
        work_dir = output_file.parent / 'work'
        work_dir.mkdir(parents=True, exist_ok=True)
        
        # Define standard directory structure
        dirs = {
            'root': work_dir,
            'audio': work_dir / 'audio',
            'segments': work_dir / 'segments',
            'encoded': work_dir / 'encoded',
            'temp': work_dir / 'temp'
        }
        
        # Create all directories
        for dir_path in dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
            
        # Track this work directory
        self._active_dirs.add(work_dir)
        
        try:
            yield dirs
        finally:
            self.cleanup(work_dir)
    
    def cleanup(self, work_dir: Path) -> None:
        """Clean up a specific work directory.
        
        Args:
            work_dir: Work directory to clean up
        """
        if work_dir in self._active_dirs:
            try:
                shutil.rmtree(work_dir)
                self._active_dirs.remove(work_dir)
                logger.info(f"Cleaned up work directory: {work_dir}")
            except Exception as e:
                logger.error(f"Failed to clean up work directory {work_dir}: {e}")
    
    def cleanup_all(self) -> None:
        """Clean up all active work directories."""
        for work_dir in list(self._active_dirs):
            self.cleanup(work_dir)
