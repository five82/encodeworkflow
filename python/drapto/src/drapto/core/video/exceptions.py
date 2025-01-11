"""Exceptions for video processing modules."""

class HDRDetectionError(Exception):
    """Raised when HDR detection fails."""
    pass


class BlackBarDetectionError(Exception):
    """Raised when black bar detection fails."""
    pass
