"""Command line interface for video encoding workflow."""

import argparse
import sys
import os
from pathlib import Path
from typing import Optional, Union, Tuple
import shutil

from loguru import logger

from . import default_config as defaults
from .config import EncodingConfig
from .video_processor import VideoProcessor
from .path_manager import PathManager
from .formatting import TerminalFormatter


def parse_path(path: str) -> Tuple[Path, str]:
    """Parse path string to Path object.
    
    Args:
        path: Path string
        
    Returns:
        Tuple of (Path object, original path string)
        
    Raises:
        argparse.ArgumentTypeError: If path is invalid
    """
    try:
        # Get base directory for videos
        base_dir = Path("/home/ken/projects/encodeworkflow/videos")
        
        # First get absolute path relative to base directory
        p = base_dir / path
        
        # Handle Silverblue path mapping
        if Path("/run/media").exists() and str(p).startswith("/media/"):
            p = Path("/run" + str(p))
            
        # Don't resolve output paths since they may not exist yet
        # and we want to preserve trailing slashes
        return p, path
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Invalid path: {e}")


def validate_preset(value: str) -> int:
    """Validate preset value.
    
    Args:
        value: Preset value string
        
    Returns:
        Preset value as integer
        
    Raises:
        argparse.ArgumentTypeError: If value is invalid
    """
    try:
        preset = int(value)
        if preset < 0 or preset > 13:
            raise ValueError("Preset must be between 0 and 13")
        return preset
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def validate_vmaf(value: str) -> float:
    """Validate VMAF value.
    
    Args:
        value: VMAF value string
        
    Returns:
        VMAF value as float
        
    Raises:
        argparse.ArgumentTypeError: If value is invalid
    """
    try:
        vmaf = float(value)
        if vmaf < 0 or vmaf > 100:
            raise ValueError("VMAF must be between 0 and 100")
        return vmaf
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def validate_positive_int(value: str) -> int:
    """Validate positive integer value.
    
    Args:
        value: Integer value string
        
    Returns:
        Value as integer
        
    Raises:
        argparse.ArgumentTypeError: If value is invalid
    """
    try:
        val = int(value)
        if val <= 0:
            raise ValueError("Value must be positive")
        return val
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Video encoding workflow",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Create subparsers
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Create encode subcommand
    encode_parser = subparsers.add_parser(
        "encode",
        help="Encode video files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Input/output options
    encode_parser.add_argument(
        "input",
        type=parse_path,
        help="Input video file or directory"
    )
    encode_parser.add_argument(
        "output",
        type=parse_path,
        help="Output video file or directory"
    )
    
    # Encoding options
    encode_parser.add_argument(
        "--target-vmaf",
        type=validate_vmaf,
        default=defaults.TARGET_VMAF,
        help="Target VMAF score"
    )
    encode_parser.add_argument(
        "--preset",
        type=validate_preset,
        default=defaults.PRESET,
        help="SVT-AV1 preset (0-13, where 0 is highest quality)"
    )
    
    # Feature flags
    encode_parser.add_argument(
        "--disable-crop",
        action="store_true",
        help="Disable automatic crop detection"
    )
    encode_parser.add_argument(
        "--disable-chunked",
        action="store_true",
        help="Disable chunked encoding"
    )
    
    # Chunked encoding options
    encode_parser.add_argument(
        "--segment-length",
        type=validate_positive_int,
        default=defaults.SEGMENT_LENGTH,
        help="Length of each segment in seconds"
    )
    encode_parser.add_argument(
        "--vmaf-sample-count",
        type=int,
        default=defaults.VMAF_SAMPLE_COUNT,
        help="Number of VMAF samples"
    )
    encode_parser.add_argument(
        "--vmaf-sample-length",
        type=validate_positive_int,
        default=defaults.VMAF_SAMPLE_LENGTH,
        help="Length of each VMAF sample in seconds"
    )
    encode_parser.add_argument(
        "--temp-dir",
        type=Path,
        help="Override default temporary directory location (defaults to input file's parent directory)"
    )
    encode_parser.add_argument(
        "--working-dir",
        type=Path,
        help="Override default working directory location"
    )
    
    # Logging options
    encode_parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    encode_parser.add_argument(
        "--log-file",
        type=parse_path,
        help="Log file path"
    )
    
    args = parser.parse_args()
    
    try:
        # Configure logging
        log_config = {
            "handlers": [{
                "sink": sys.stderr,
                "level": args.log_level,
                "format": "<level>{message}</level>",
                "colorize": True
            }]
        }
        if args.log_file:
            log_config["handlers"].append({
                "sink": args.log_file[0],
                "level": args.log_level,
                "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
            })
        logger.configure(**log_config)
        
        if args.command == "encode":
            # Print tool paths
            fmt = TerminalFormatter()
            fmt.print_header("Tool Paths")
            print(f"{fmt.bold}FFmpeg:   {fmt.reset}{defaults.FFMPEG}")
            print(f"{fmt.bold}FFprobe:  {fmt.reset}{defaults.FFPROBE}")
            print(f"{fmt.bold}ab-av1:   {fmt.reset}{shutil.which('ab-av1') or 'Not found'}")
            print()
            
            # Create path manager
            try:
                paths = PathManager(args.input[0], args.output[0], args.output[1])
            except Exception as e:
                logger.error(f"Path error: {e}")
                return 1
            
            # Create configuration
            config = EncodingConfig(
                target_vmaf=args.target_vmaf,
                preset=args.preset,
                vmaf_sample_count=args.vmaf_sample_count,
                vmaf_sample_length=args.vmaf_sample_length,
                disable_crop=args.disable_crop,
                enable_chunked_encoding=not args.disable_chunked,
                segment_length=args.segment_length,
                working_dir=args.working_dir,
                temp_dir=args.temp_dir
            )
            
            # Process video
            processor = VideoProcessor(config)
            if args.input[0].is_dir():
                # Check if input directory has video files
                video_extensions = {'.mp4', '.mkv', '.mov', '.avi', '.wmv'}
                has_videos = any(f.suffix.lower() in video_extensions for f in args.input[0].rglob('*'))
                if not has_videos:
                    raise ValueError(f"No video files found in input directory: {args.input[0]}")
                    
                processor.process_directory(args.input[0], paths.output_dir)
            else:
                # Validate input is a video file
                video_extensions = {'.mp4', '.mkv', '.mov', '.avi', '.wmv'}
                if args.input[0].suffix.lower() not in video_extensions:
                    raise ValueError(f"Input file is not a recognized video format: {args.input[0]}")
                    
                # Check if output directory is writable
                if not os.access(paths.output_dir, os.W_OK):
                    raise PermissionError(f"Output directory is not writable: {paths.output_dir}")
                    
                processor.process_video(args.input[0], paths.output_file)
        
        return 0
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except PermissionError as e:
        logger.error(f"Permission error: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.log_level == "DEBUG":
            logger.exception("Detailed error:")
        return 1


if __name__ == "__main__":
    sys.exit(main())
