"""Command line interface for video encoding workflow."""

import argparse
import sys
from pathlib import Path
from typing import Optional, Union

from loguru import logger

from . import default_config as defaults
from .config import EncodingConfig
from .video_processor import VideoProcessor


def parse_path(path: str) -> Path:
    """Parse path string to Path object.
    
    Args:
        path: Path string
        
    Returns:
        Path object
        
    Raises:
        argparse.ArgumentTypeError: If path is invalid
    """
    try:
        p = Path(path).resolve()
        # Handle Silverblue path mapping
        if Path("/run/media").exists() and str(p).startswith("/media/"):
            p = Path("/run" + str(p))
        return p
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
        default=30,
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
            "handlers": [{"sink": sys.stderr, "level": args.log_level}]
        }
        if args.log_file:
            log_config["handlers"].append({"sink": args.log_file, "level": args.log_level})
        logger.configure(**log_config)
        
        if args.command == "encode":
            # Convert paths to absolute
            input_path = args.input.resolve()
            output_path = args.output.resolve()
            
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
            if input_path.is_dir():
                # Create output directory if it doesn't exist
                output_path.mkdir(parents=True, exist_ok=True)
                if not output_path.is_dir():
                    raise ValueError("Output must be a directory when input is a directory")
                processor.process_directory(input_path, output_path)
            else:
                # Create parent directories for output file if needed
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if output_path.is_dir():
                    raise ValueError("Output must be a file when input is a file")
                processor.process_video(input_path, output_path)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.log_level == "DEBUG":
            logger.exception("Detailed error:")
        return 1


if __name__ == "__main__":
    sys.exit(main())
