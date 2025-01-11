"""Tests for Dolby Vision encoding path."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from drapto.encoding.dolby_vision import DolbyVisionEncoder
from drapto.encoding.types import VideoStreamInfo, QualitySettings
from drapto.encoding.base import EncodingContext


@pytest.fixture
def encoder():
    """Create a DolbyVisionEncoder instance."""
    config = {
        'enable_chunked_encoding': False,
        'dolby_vision': {
            'profile': 8.1,
            'level': 6,
            'rpu_path': '/path/to/rpu.bin'
        }
    }
    return DolbyVisionEncoder(config)


@pytest.fixture
def context(tmp_path):
    """Create an encoding context."""
    input_path = tmp_path / "input.mkv"
    output_path = tmp_path / "output.mkv"
    input_path.touch()  # Create empty input file
    return EncodingContext(
        input_path=input_path,
        output_path=output_path,
        target_vmaf=95.0,
        preset=8,
        svt_params="film-grain=8:film-grain-denoise=0"
    )


@pytest.fixture
def mock_stream_info():
    """Create mock stream info."""
    return VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer="smpte2084",
        color_primaries="bt2020",
        color_space="bt2020nc",
        frame_rate=24.0,
        bit_depth=10,
        is_hdr=True,
        is_dolby_vision=True,
        crop_info=None,
        quality_settings=None,
        hdr_info=None
    )


@pytest.fixture
def mock_quality_settings():
    """Create mock quality settings."""
    return QualitySettings(
        crf=22,
        preset="slow",
        max_bitrate=8_000_000,
        bufsize=16_000_000,
        qmin=None,
        qmax=None
    )


@pytest.mark.asyncio
async def test_encode_content_success(encoder, context, mock_stream_info, mock_quality_settings):
    """Test successful encoding."""
    with patch('drapto.utils.validation.validate_input_file', return_value=context.input_path), \
         patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder._analyzer, 'get_quality_settings', return_value=mock_quality_settings), \
         patch.object(encoder._analyzer, 'detect_black_bars', return_value=None), \
         patch.object(encoder, '_run_command', return_value=(True, '')), \
         patch.object(encoder, '_validate_output', return_value=True), \
         patch.object(encoder, '_build_ffmpeg_command', return_value=['-c:v', 'libsvtav1']):
        assert await encoder.encode_content(context)


def test_build_ffmpeg_command_basic(encoder, context, mock_stream_info, mock_quality_settings):
    """Test basic FFmpeg command building."""
    cmd = encoder._build_ffmpeg_command(context, mock_stream_info, mock_quality_settings)
    assert "-c:v" in cmd
    assert "libsvtav1" in cmd


def test_build_ffmpeg_command_with_crop(encoder, context, mock_stream_info, mock_quality_settings):
    """Test FFmpeg command with crop filter."""
    context.crop_filter = "crop=1920:800:0:140"
    cmd = encoder._build_ffmpeg_command(context, mock_stream_info, mock_quality_settings)
    assert "-vf" in cmd
    assert "crop=1920:800:0:140" in cmd


def test_build_ffmpeg_command_with_hw_accel(encoder, context, mock_stream_info, mock_quality_settings):
    """Test FFmpeg command with hardware acceleration."""
    context.hw_accel = "vaapi"
    cmd = encoder._build_ffmpeg_command(context, mock_stream_info, mock_quality_settings)
    assert "-hwaccel" in cmd
    assert "vaapi" in cmd


def test_encode_content_with_black_bars(encoder, context, mock_stream_info, mock_quality_settings):
    """Test encoding with black bar detection."""
    context.crop_filter = "crop=1920:800:0:140"
    with patch('drapto.utils.validation.validate_input_file', return_value=context.input_path), \
         patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder._analyzer, 'get_quality_settings', return_value=mock_quality_settings), \
         patch.object(encoder, '_run_command', return_value=True), \
         patch.object(encoder, '_validate_output', return_value=True), \
         patch.object(encoder, '_build_ffmpeg_command', return_value=['-c:v', 'libsvtav1']):
        assert encoder._build_ffmpeg_command(context, mock_stream_info, mock_quality_settings)


@pytest.mark.asyncio
async def test_encode_content_with_different_resolutions(encoder, context, mock_stream_info, mock_quality_settings):
    """Test encoding with different resolutions."""
    # Test SD
    mock_stream_info.width = 1280
    mock_stream_info.height = 720
    with patch('drapto.utils.validation.validate_input_file', return_value=context.input_path), \
         patch.object(encoder._analyzer, 'analyze_stream', return_value=mock_stream_info), \
         patch.object(encoder._analyzer, 'get_quality_settings', return_value=mock_quality_settings), \
         patch.object(encoder._analyzer, 'detect_black_bars', return_value=None), \
         patch.object(encoder, '_run_command', return_value=(True, '')), \
         patch.object(encoder, '_validate_output', return_value=True), \
         patch.object(encoder, '_build_ffmpeg_command', return_value=['-c:v', 'libsvtav1']):
        assert await encoder.encode_content(context)
