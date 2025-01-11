"""Video analysis error types."""

from typing import Optional


class VideoAnalysisError(Exception):
    """Base class for video analysis errors."""
    
    def __init__(self, message: str, details: Optional[str] = None):
        """Initialize error.
        
        Args:
            message: Error message
            details: Optional technical details
        """
        self.message = message
        self.details = details
        super().__init__(message)


class StreamAnalysisError(VideoAnalysisError):
    """Error analyzing video stream properties."""
    pass


class HDRDetectionError(VideoAnalysisError):
    """Error detecting HDR format."""
    pass


class BlackBarDetectionError(VideoAnalysisError):
    """Error detecting black bars."""
    pass


class CropValidationError(VideoAnalysisError):
    """Error validating crop values."""
    
    def __init__(self, message: str, original_width: int, original_height: int,
                 crop_width: int, crop_height: int, x_offset: int, y_offset: int):
        """Initialize error.
        
        Args:
            message: Error message
            original_width: Original video width
            original_height: Original video height
            crop_width: Proposed crop width
            crop_height: Proposed crop height
            x_offset: Proposed X offset
            y_offset: Proposed Y offset
        """
        details = (
            f"Original: {original_width}x{original_height}, "
            f"Crop: {crop_width}x{crop_height}, "
            f"Offset: ({x_offset}, {y_offset})"
        )
        super().__init__(message, details)
        self.original_width = original_width
        self.original_height = original_height
        self.crop_width = crop_width
        self.crop_height = crop_height
        self.x_offset = x_offset
        self.y_offset = y_offset


class QualitySettingsError(VideoAnalysisError):
    """Error determining quality settings."""
    pass


class FFmpegError(VideoAnalysisError):
    """Error running FFmpeg command."""
    
    def __init__(self, message: str, cmd: Optional[str] = None, 
                 stderr: Optional[str] = None):
        """Initialize error.
        
        Args:
            message: Error message
            cmd: FFmpeg command that failed
            stderr: FFmpeg error output
        """
        details = f"Command: {cmd}\nError: {stderr}" if cmd else stderr
        super().__init__(message, details)
        self.cmd = cmd
        self.stderr = stderr


class MediaInfoError(VideoAnalysisError):
    """Error running mediainfo command."""
    
    def __init__(self, message: str, cmd: Optional[str] = None, 
                 stderr: Optional[str] = None):
        """Initialize error.
        
        Args:
            message: Error message
            cmd: MediaInfo command that failed
            stderr: MediaInfo error output
        """
        details = f"Command: {cmd}\nError: {stderr}" if cmd else stderr
        super().__init__(message, details)
        self.cmd = cmd
        self.stderr = stderr
