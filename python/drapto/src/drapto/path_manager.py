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
        logger.debug("Initializing PathManager")
        logger.debug(f"Initial paths:")
        logger.debug(f"  Input path (raw): {input_path}")
        logger.debug(f"  Output path (raw): {output_path}")
        logger.debug(f"  Output string (raw): {output_path_str}")
        logger.debug(f"  Current working dir: {Path.cwd()}")

        # Convert to Path objects and resolve relative to current directory
        self.input = Path(input_path)
        logger.debug(f"Input path after Path conversion: {self.input}")
        logger.debug(f"Input path is absolute? {self.input.is_absolute()}")
        
        if not self.input.is_absolute():
            logger.debug("Input path is relative, resolving against cwd")
            self.input = Path.cwd() / self.input
            logger.debug(f"Input path after cwd resolution: {self.input}")
        
        self.input = self.input.resolve()
        logger.debug(f"Final resolved input path: {self.input}")
        
        # Keep original output path string to check if it was intended as a directory
        output = Path(output_path)
        logger.debug(f"Output path after Path conversion: {output}")
        logger.debug(f"Output path is absolute? {output.is_absolute()}")
        
        if not output.is_absolute():
            logger.debug("Output path is relative, resolving against cwd")
            output = Path.cwd() / output
            logger.debug(f"Output path after cwd resolution: {output}")
        
        logger.debug("Final raw paths:")
        logger.debug(f"  Input: {self.input}")
        logger.debug(f"  Output: {output}")
        
        # Validate input exists
        if not self.input.exists():
            logger.error(f"Input path does not exist: {self.input}")
            logger.debug(f"Parent directory exists? {self.input.parent.exists()}")
            if self.input.parent.exists():
                logger.debug(f"Contents of parent directory: {list(self.input.parent.iterdir())}")
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
