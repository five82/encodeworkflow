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
