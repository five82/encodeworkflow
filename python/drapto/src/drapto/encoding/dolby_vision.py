"""Dolby Vision encoder implementation."""

import logging
from pathlib import Path
from typing import List, Optional

from drapto.core.base import BaseEncoder, EncodingContext
from drapto.core.video.types import VideoStreamInfo
from drapto.core.video.analysis import VideoAnalyzer


class DolbyVisionEncoder(BaseEncoder):
    """Encoder for Dolby Vision content using FFmpeg."""
    
    def __init__(self, config):
        """Initialize encoder.
        
        Args:
            config: Encoder configuration
        """
        super().__init__(config)
        self._analyzer = VideoAnalyzer(config)
        self._logger = logging.getLogger(__name__)
        
    async def encode_content(self, context: EncodingContext) -> bool:
        """Encode Dolby Vision content.
        
        Args:
            context: Encoding context with input/output paths
            
        Returns:
            True if encoding successful, False otherwise
        """
        try:
            # Analyze input stream
            stream_info = self._analyzer.analyze_stream(context.input_path)
            if not stream_info:
                self._logger.error("Failed to analyze input stream")
                return False
                
            if not stream_info.is_dolby_vision:
                self._logger.error("Input does not contain Dolby Vision metadata")
                return False
                
            # Get quality settings
            quality_settings = self._analyzer.get_quality_settings(stream_info)
            
            # Detect black bars
            crop_filter = self._analyzer.detect_black_bars(context.input_path)
            if crop_filter:
                context.crop_filter = crop_filter
                
            # Build and run FFmpeg command
            cmd = self._build_ffmpeg_command(context, stream_info, quality_settings)
            if not await self._run_command(cmd):
                return False
                
            # Validate output
            if not await self._validate_output(context.output_path):
                return False
                
            return True
            
        except Exception as e:
            self._logger.error(f"Encoding failed: {e}")
            return False
            
    def _build_ffmpeg_command(self, context: EncodingContext, 
                            stream_info: VideoStreamInfo,
                            quality_settings) -> List[str]:
        """Build FFmpeg command for encoding.
        
        Args:
            context: Encoding context
            stream_info: Video stream information
            quality_settings: Quality settings for encoding
            
        Returns:
            List of command arguments
        """
        cmd = [
            self.config.get('ffmpeg', 'ffmpeg'),
            '-y',  # Overwrite output
            '-hide_banner'
        ]
        
        # Add hardware acceleration if available
        hw_opts = self.config.get('hw_accel_opts')
        if hw_opts:
            cmd.extend(hw_opts.split())
            
        # Input
        cmd.extend(['-i', str(context.input_path)])
        
        # Video filters
        filters = []
        if context.crop_filter:
            filters.append(context.crop_filter)
        if filters:
            cmd.extend(['-vf', ','.join(filters)])
            
        # Video codec settings
        cmd.extend([
            '-c:v', 'libsvtav1',
            '-preset', str(context.preset),
            '-crf', str(quality_settings.crf)
        ])
        
        # HDR settings
        if stream_info.is_hdr:
            cmd.extend([
                '-pix_fmt', stream_info.pixel_format,
                '-color_primaries', stream_info.color_primaries,
                '-color_trc', stream_info.color_transfer,
                '-colorspace', stream_info.color_space
            ])
            
        # SVT-AV1 params
        if context.svt_params:
            cmd.extend(['-svtav1-params', context.svt_params])
            
        # Audio and subtitle settings
        cmd.extend([
            '-c:a', 'copy',
            '-c:s', 'copy'
        ])
        
        # Output
        cmd.append(str(context.output_path))
        
        return cmd

    async def _validate_output(self, output_path: Path) -> bool:
        # TO DO: implement output validation
        return True
