"""Video analysis and stream detection utilities."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

@dataclass
class VideoStreamInfo:
    """Information about a video stream."""
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

class VideoAnalyzer:
    """Video stream analysis utilities."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize analyzer with config."""
        self.config = config
        self._logger = logging.getLogger(__name__)
        
    def analyze_stream(self, input_path: Path) -> Optional[VideoStreamInfo]:
        """Analyze video stream and return information.
        
        Args:
            input_path: Path to input video file
            
        Returns:
            VideoStreamInfo if successful, None if analysis fails
        """
        try:
            # Get stream info using FFprobe
            cmd = [
                self.config.get('ffprobe', 'ffprobe'),
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 
                'stream=width,height,r_frame_rate,pix_fmt,'
                'color_transfer,color_primaries,color_space,bits_per_raw_sample',
                '-of', 'json',
                str(input_path)
            ]
            result = json.loads(subprocess.check_output(cmd).decode())
            
            if not result.get('streams'):
                self._logger.error("No video streams found")
                return None
                
            stream = result['streams'][0]
            
            # Parse frame rate fraction
            fps_num, fps_den = map(int, stream.get('r_frame_rate', '0/1').split('/'))
            frame_rate = fps_num / fps_den if fps_den != 0 else 0.0
            
            # Create stream info
            info = VideoStreamInfo(
                width=int(stream.get('width', 0)),
                height=int(stream.get('height', 0)),
                color_transfer=stream.get('color_transfer'),
                color_primaries=stream.get('color_primaries'),
                color_space=stream.get('color_space'),
                pixel_format=stream.get('pix_fmt', 'yuv420p'),
                frame_rate=frame_rate,
                bit_depth=int(stream.get('bits_per_raw_sample', 8))
            )
            
            # Detect HDR
            info.is_hdr = self._is_hdr_content(info)
            
            # Detect Dolby Vision
            info.is_dolby_vision = self._has_dolby_vision(input_path)
            
            return info
            
        except Exception as e:
            self._logger.error(f"Stream analysis failed: {e}")
            return None
            
    def get_stream_size(self, input_path: Path) -> Optional[int]:
        """Get size of video stream in bytes.
        
        Args:
            input_path: Path to input file
            
        Returns:
            Size in bytes if successful, None if failed
        """
        try:
            cmd = [
                self.config.get('ffprobe', 'ffprobe'),
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=size',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(input_path)
            ]
            size = subprocess.check_output(cmd).decode().strip()
            return int(size) if size else None
        except Exception as e:
            self._logger.error(f"Failed to get stream size: {e}")
            return None
            
    def detect_black_bars(self, input_path: Path, stream_info: VideoStreamInfo) -> Optional[str]:
        """Detect black bars and return crop filter.
        
        Args:
            input_path: Path to input file
            stream_info: Video stream information
            
        Returns:
            Crop filter string if black bars detected, None otherwise
        """
        if self.config.get('disable_crop', False):
            self._logger.info("Crop detection disabled")
            return None
            
        try:
            # Set crop threshold based on HDR status
            crop_threshold = 128 if stream_info.is_hdr else 16
            
            # Sample frames for black bar detection
            cmd = [
                self.config.get('ffmpeg', 'ffmpeg'),
                '-hide_banner',
                '-i', str(input_path),
                '-vf', f'blackdetect=d=0:pix_th={crop_threshold/255}',
                '-f', 'null',
                '-'
            ]
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode()
            
            # Parse black bar detection output
            # TODO: Implement parsing logic
            return None
            
        except Exception as e:
            self._logger.error(f"Black bar detection failed: {e}")
            return None
            
    def get_quality_settings(self, stream_info: VideoStreamInfo) -> Tuple[int, str]:
        """Get quality settings based on resolution and HDR status.
        
        Args:
            stream_info: Video stream information
            
        Returns:
            Tuple of (crf value, pixel format)
        """
        # Select CRF based on resolution
        if stream_info.width <= 1280:
            crf = self.config.get('crf_sd', 25)
        elif stream_info.width <= 1920:
            crf = self.config.get('crf_hd', 25)
        else:
            crf = self.config.get('crf_uhd', 29)
            
        # Select pixel format
        if stream_info.is_hdr or stream_info.is_dolby_vision:
            pix_fmt = 'yuv420p10le'  # 10-bit for HDR
        else:
            pix_fmt = 'yuv420p'  # 8-bit for SDR
            
        return crf, pix_fmt
        
    def _is_hdr_content(self, info: VideoStreamInfo) -> bool:
        """Check if content is HDR based on color information."""
        hdr_transfers = {'smpte2084', 'arib-std-b67', 'smpte428', 'bt2020-10', 'bt2020-12'}
        hdr_primaries = {'bt2020'}
        hdr_spaces = {'bt2020nc', 'bt2020c'}
        
        return (
            (info.color_transfer in hdr_transfers) or
            (info.color_primaries in hdr_primaries) or
            (info.color_space in hdr_spaces)
        )
        
    def _has_dolby_vision(self, input_path: Path) -> bool:
        """Check if file contains Dolby Vision metadata."""
        try:
            cmd = ['mediainfo', str(input_path)]
            output = subprocess.check_output(cmd).decode()
            return 'Dolby Vision' in output
        except Exception as e:
            self._logger.error(f"Dolby Vision detection failed: {e}")
            return False
