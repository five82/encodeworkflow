"""Path management for drapto."""

from pathlib import Path
from typing import Dict

from loguru import logger


class PathManager:
    """Manages all paths for video processing."""
    
    def __init__(self, input_path: str | Path, output_path: str | Path, output_path_str: str):
        """Initialize path manager.
        
        Args:
            input_path: Input file or directory path
            output_path: Output file or directory path
            output_path_str: Original output path string (used to check if it was intended as a directory)
        """
        # Get base directory for videos
        base_dir = Path("/home/ken/projects/encodeworkflow/videos")
        
        # Convert to Path objects but don't resolve yet
        self.input = Path(input_path)
        if not self.input.is_absolute():
            self.input = base_dir / self.input
        self.input = self.input.resolve()
        
        # Keep original output path string to check if it was intended as a directory
        output = Path(output_path)
        if not output.is_absolute():
            output = base_dir / output
        
        logger.debug(f"Raw paths:")
        logger.debug(f"  Input path: {input_path}")
        logger.debug(f"  Output path: {output_path}")
        logger.debug(f"  Original output string: {output_path_str}")
        logger.debug(f"  Base dir: {base_dir}")
        
        # Validate input exists
        if not self.input.exists():
            raise FileNotFoundError(f"Input does not exist: {self.input}")
            
        # Determine if input is directory
        self.input_is_dir = self.input.is_dir()
        
        # Handle output path
        logger.debug(f"Processing output path: {output}")
        logger.debug(f"  Is directory? {output.is_dir()}")
        logger.debug(f"  Original ends with slash? {output_path_str.endswith(('/', '\\'))}")
        
        if output_path_str.endswith(('/', '\\')):  # Output is explicitly a directory
            logger.debug("Output is explicitly a directory")
            self.output_dir = output
            self.output_file = self.output_dir / f"{self.input.stem}.mkv"
        elif output.is_dir():  # Output exists and is a directory
            logger.debug("Output exists and is a directory")
            self.output_dir = output
            self.output_file = self.output_dir / f"{self.input.stem}.mkv"
        else:  # Output is a file
            logger.debug("Output is a file")
            self.output_dir = output.parent
            self.output_file = output
            if not str(self.output_file).lower().endswith('.mkv'):
                self.output_file = self.output_file.with_suffix('.mkv')
        
        logger.debug(f"Final paths:")
        logger.debug(f"  Input: {self.input}")
        logger.debug(f"  Output dir: {self.output_dir}")
        logger.debug(f"  Output file: {self.output_file}")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Work directory is always in output directory
        self.work_dir = self.output_dir / 'work'
        
        logger.debug(f"PathManager initialized with:")
        logger.debug(f"  Input: {self.input}")
        logger.debug(f"  Output dir: {self.output_dir}")
        logger.debug(f"  Output file: {self.output_file}")
        logger.debug(f"  Work dir: {self.work_dir}")
    
    @property
    def work_paths(self) -> Dict[str, Path]:
        """Get work directory paths.
        
        Returns:
            Dictionary of work directory paths
        """
        return {
            'root': self.work_dir,
            'audio': self.work_dir / 'audio',
            'segments': self.work_dir / 'segments',
            'encoded': self.work_dir / 'encoded',
            'temp': self.work_dir / 'temp'
        }
    
    def create_work_dirs(self):
        """Create all work directories."""
        for path in self.work_paths.values():
            path.mkdir(parents=True, exist_ok=True)
    
    def cleanup_work_dirs(self):
        """Clean up work directories."""
        import shutil
        if self.work_dir.exists():
            logger.info(f"Cleaning up work directory: {self.work_dir}")
            try:
                shutil.rmtree(self.work_dir)
            except Exception as e:
                logger.error(f"Failed to clean up work directory: {e}")
