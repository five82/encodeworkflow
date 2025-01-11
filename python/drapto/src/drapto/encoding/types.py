"""Type definitions for video encoding."""

from dataclasses import dataclass
from typing import Optional, Union


@dataclass
class QualitySettings:
    """Encoding quality settings.
    
    Attributes:
        crf: Constant Rate Factor (quality-based VBR)
        preset: Encoding preset (slower = better quality)
        max_bitrate: Maximum bitrate in bits/s
        bufsize: VBV buffer size in bits
        qmin: Minimum quantizer scale
        qmax: Maximum quantizer scale
    """
    crf: int
    preset: str
    max_bitrate: int
    bufsize: int
    qmin: Optional[int] = None
    qmax: Optional[int] = None


@dataclass
class HDRInfo:
    """HDR detection results.
    
    Attributes:
        is_hdr: Whether the stream is HDR
        is_dolby_vision: Whether the stream has Dolby Vision metadata
        hdr_format: HDR format if detected (HDR10, HDR10+, HLG, Dolby Vision)
        black_level: Black level threshold for HDR content
    """
    is_hdr: bool = False
    is_dolby_vision: bool = False
    hdr_format: Optional[str] = None
    black_level: Optional[int] = None


@dataclass
class CropInfo:
    """Crop detection results.
    
    Attributes:
        x: X offset for cropping
        y: Y offset for cropping
        width: Width after cropping
        height: Height after cropping
        enabled: Whether cropping should be applied
    """
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    enabled: bool = False


@dataclass
class VideoStreamInfo:
    """Information about a video stream.
    
    Attributes:
        width: Video width in pixels
        height: Video height in pixels
        color_transfer: Color transfer characteristics (e.g. bt709, smpte2084)
        color_primaries: Color primaries (e.g. bt709, bt2020)
        color_space: Color space (e.g. bt709, bt2020nc)
        pixel_format: Pixel format (e.g. yuv420p, yuv420p10le)
        frame_rate: Frame rate in frames per second
        bit_depth: Bits per color component
        is_hdr: Whether the stream is HDR
        is_dolby_vision: Whether the stream has Dolby Vision metadata
        crop_info: Optional black bar detection info
        quality_settings: Optional encoding quality settings
        hdr_info: Optional HDR detection info
    """
    width: int
    height: int
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None
    color_space: Optional[str] = None
    pixel_format: str = 'yuv420p'
    frame_rate: float = 0.0
    bit_depth: int = 8
    is_hdr: bool = False
    is_dolby_vision: bool = False
    crop_info: Optional[CropInfo] = None
    quality_settings: Optional[QualitySettings] = None
    hdr_info: Optional[HDRInfo] = None
