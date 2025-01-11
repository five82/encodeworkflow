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
        """Encode video content.
        
        Args:
            context: Encoding context
            
        Returns:
            True if encoding successful, False otherwise
        """
        try:
            # Validate input file and resources
            if not await self._validate_input(context):
                return False
                
            # Check dependencies
            if not self._check_dependencies():
                return False
            
            # Analyze input stream
            stream_info = await self._analyze_stream(context)
            if not stream_info:
                raise RuntimeError("Failed to analyze input stream")
            
            # Get quality settings
            quality_settings = await self._get_quality_settings(context, stream_info)
            if not quality_settings:
                raise RuntimeError("Failed to get quality settings")
            
            # Detect black bars
            crop_filter = self._analyzer.detect_black_bars(context.input_path)
            if crop_filter:
                context.crop_filter = crop_filter
                
            # Build and run FFmpeg command
            cmd = self._build_ffmpeg_command(context, stream_info, quality_settings)
            if not cmd:
                raise RuntimeError("Failed to build FFmpeg command")
                
            success = await self._run_command(cmd)
            if not success:
                raise RuntimeError("FFmpeg command failed")
            
            # Validate output
            if not await self._validate_output(context):
                raise RuntimeError("Output validation failed")
            
            return True
            
        except Exception as e:
            self._logger.error(f"Encoding failed: {str(e)}")
            return False
            
    def _build_ffmpeg_command(
        self,
        context: EncodingContext,
        stream_info: VideoStreamInfo,
        quality_settings
    ) -> List[str]:
        """Build FFmpeg command for encoding.
        
        Args:
            context: Encoding context
            stream_info: Video stream information
            quality_settings: Quality settings for encoding
            
        Returns:
            List of command arguments
        """
        cmd = ['ffmpeg', '-y', '-hide_banner']
        
        # Add hardware acceleration if specified
        if context.hw_accel:
            cmd.extend(['-hwaccel', context.hw_accel])
        
        # Input file
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
            '-crf', str(quality_settings.crf),
            '-b:v', str(quality_settings.max_bitrate),
            '-maxrate', str(quality_settings.max_bitrate),
            '-bufsize', str(quality_settings.bufsize)
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
        
        # Dolby Vision settings
        dv_config = self.config.get('dolby_vision', {})
        cmd.extend([
            '-profile:v', str(dv_config.get('profile', 8.1)),
            '-level:v', str(dv_config.get('level', 6)),
            '-metadata:s:v', f'dv_profile={dv_config.get("profile", 8.1)}',
            '-metadata:s:v', f'dv_level={dv_config.get("level", 6)}'
        ])
        
        # Output
        cmd.append(str(context.output_path))
        
        return cmd

    async def _validate_output(self, output_path: Path) -> bool:
        # TO DO: implement output validation
        return True

    async def _validate_input(self, context: EncodingContext) -> bool:
        # TO DO: implement input validation
        return True

    def _check_dependencies(self) -> bool:
        # TO DO: implement dependency check
        return True

    async def _analyze_stream(self, context: EncodingContext) -> Optional[VideoStreamInfo]:
        """Analyze input stream.
        
        Args:
            context: Encoding context
            
        Returns:
            Stream information if successful, None otherwise
        """
        try:
            # Analyze input stream
            stream_info = self._analyzer.analyze_stream(context.input_path)
            if not stream_info:
                self._logger.error("Failed to analyze input stream")
                return None
                
            # Check for Dolby Vision metadata
            if not stream_info.is_dolby_vision:
                self._logger.error("Input does not contain Dolby Vision metadata")
                return None
                
            # Detect black bars if needed
            if not context.crop_filter:
                try:
                    crop_filter = self._analyzer.detect_black_bars(context.input_path)
                    if crop_filter:
                        context.crop_filter = crop_filter
                except Exception as e:
                    self._logger.warning(f"Black bar detection failed: {str(e)}")
                    # Continue without crop filter
                    pass
                    
            return stream_info
            
        except Exception as e:
            self._logger.error(f"Stream analysis failed: {str(e)}")
            return None

    async def _get_quality_settings(self, context: EncodingContext, stream_info: VideoStreamInfo):
        # Get quality settings
        quality_settings = self._analyzer.get_quality_settings(stream_info)
        return quality_settings
