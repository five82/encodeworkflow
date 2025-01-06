"""Tests for the Dolby Vision encoding path."""

import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import Mock, patch

from drapto.core.base import EncodingContext
from drapto.encoding.dolby_vision import DolbyVisionEncoder
from drapto.encoding.video_analysis import VideoAnalyzer, VideoStreamInfo

@pytest.fixture
def encoder():
    """Create encoder instance."""
    config = {
        'ffmpeg': 'ffmpeg',
        'ffprobe': 'ffprobe',
        'pix_fmt': 'yuv420p10le',
        'hw_accel_opts': None,
        'min_disk_gb': 50.0,
        'max_cpu_percent': 90.0,
        'max_memory_percent': 90.0,
        'disk_buffer_factor': 1.5,
        'crf_sd': 25,
        'crf_hd': 25,
        'crf_uhd': 29
    }
    return DolbyVisionEncoder(config)

@pytest.fixture
def context(tmp_path):
    """Create encoding context."""
    input_file = tmp_path / "input.mkv"
    output_file = tmp_path / "output.mkv"
    
    # Create dummy input file
    input_file.write_bytes(b"test")
    
    return EncodingContext(
        input_path=input_file,
        output_path=output_file,
        target_vmaf=95,
        preset=8,
        svt_params="film-grain=8:film-grain-denoise=0",
        crop_filter=None
    )

@pytest.fixture
def mock_stream_info():
    """Create mock stream info."""
    return VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='smpte2084',
        color_primaries='bt2020',
        color_space='bt2020nc',
        pixel_format='yuv420p10le',
        frame_rate=24.0,
        bit_depth=10,
        is_hdr=True,
        is_dolby_vision=True
    )

@pytest.mark.asyncio
async def test_encode_content_success(encoder, context, mock_stream_info):
    """Test successful encoding."""
    with patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder, '_run_command', return_value=True), \
         patch.object(encoder, '_validate_output', return_value=True):
        assert await encoder.encode_content(context)

@pytest.mark.asyncio
async def test_encode_content_not_dolby_vision(encoder, context, mock_stream_info):
    """Test encoding fails when not Dolby Vision."""
    mock_stream_info.is_dolby_vision = False
    with patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info):
        assert not await encoder.encode_content(context)

@pytest.mark.asyncio
async def test_encode_content_command_fail(encoder, context, mock_stream_info):
    """Test encoding fails when command fails."""
    with patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder, '_run_command', return_value=False):
        assert not await encoder.encode_content(context)

def test_build_ffmpeg_command_basic(encoder, context, mock_stream_info):
    """Test basic FFmpeg command building."""
    cmd = encoder._build_ffmpeg_command(context, mock_stream_info, 29, 'yuv420p10le')
    assert cmd[0] == 'ffmpeg'
    assert '-i' in cmd
    assert str(context.input_path) in cmd
    assert str(context.output_path) in cmd
    assert '-c:v' in cmd
    assert 'libsvtav1' in cmd
    assert '-preset' in cmd
    assert str(context.preset) in cmd
    assert '-crf' in cmd
    assert '29' in cmd
    assert '-pix_fmt' in cmd
    assert 'yuv420p10le' in cmd

def test_build_ffmpeg_command_with_crop(encoder, context, mock_stream_info):
    """Test FFmpeg command with crop filter."""
    context.crop_filter = "crop=1920:1080:0:140"
    cmd = encoder._build_ffmpeg_command(context, mock_stream_info, 29, 'yuv420p10le')
    assert '-vf' in cmd
    assert context.crop_filter in cmd

def test_build_ffmpeg_command_with_hw_accel(encoder, context, mock_stream_info):
    """Test FFmpeg command with hardware acceleration."""
    encoder.config['hw_accel_opts'] = '-hwaccel cuda -hwaccel_output_format cuda'
    cmd = encoder._build_ffmpeg_command(context, mock_stream_info, 29, 'yuv420p10le')
    assert '-hwaccel' in cmd
    assert 'cuda' in cmd

@pytest.mark.asyncio
async def test_encode_content_with_black_bars(encoder, context, mock_stream_info):
    """Test encoding with black bar detection."""
    with patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder._analyzer, 'detect_black_bars', return_value='crop=1920:800:0:140'), \
         patch.object(encoder, '_run_command', return_value=True), \
         patch.object(encoder, '_validate_output', return_value=True):
        assert await encoder.encode_content(context)
        assert context.crop_filter == 'crop=1920:800:0:140'

@pytest.mark.asyncio
async def test_encode_content_with_different_resolutions(encoder, context, mock_stream_info):
    """Test encoding with different resolutions."""
    # Test SD
    mock_stream_info.width = 1280
    mock_stream_info.height = 720
    with patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder, '_run_command', return_value=True), \
         patch.object(encoder, '_validate_output', return_value=True):
        assert await encoder.encode_content(context)
        
    # Test HD
    mock_stream_info.width = 1920
    mock_stream_info.height = 1080
    with patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder, '_run_command', return_value=True), \
         patch.object(encoder, '_validate_output', return_value=True):
        assert await encoder.encode_content(context)
        
    # Test UHD
    mock_stream_info.width = 3840
    mock_stream_info.height = 2160
    with patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder, '_run_command', return_value=True), \
         patch.object(encoder, '_validate_output', return_value=True):
        assert await encoder.encode_content(context)
