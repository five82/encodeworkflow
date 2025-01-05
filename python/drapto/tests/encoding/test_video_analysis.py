"""Tests for video analysis utilities."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from drapto.encoding.video_analysis import VideoAnalyzer, VideoStreamInfo

@pytest.fixture
def analyzer():
    """Create analyzer instance."""
    config = {
        'ffmpeg': 'ffmpeg',
        'ffprobe': 'ffprobe',
        'disable_crop': False
    }
    return VideoAnalyzer(config)

@pytest.fixture
def mock_ffprobe_sdr():
    """Mock FFprobe output for SDR content."""
    return json.dumps({
        'streams': [{
            'width': 1920,
            'height': 1080,
            'r_frame_rate': '24/1',
            'pix_fmt': 'yuv420p',
            'color_transfer': 'bt709',
            'color_primaries': 'bt709',
            'color_space': 'bt709',
            'bits_per_raw_sample': '8'
        }]
    })

@pytest.fixture
def mock_ffprobe_hdr():
    """Mock FFprobe output for HDR content."""
    return json.dumps({
        'streams': [{
            'width': 3840,
            'height': 2160,
            'r_frame_rate': '24/1',
            'pix_fmt': 'yuv420p10le',
            'color_transfer': 'smpte2084',
            'color_primaries': 'bt2020',
            'color_space': 'bt2020nc',
            'bits_per_raw_sample': '10'
        }]
    })

@pytest.mark.asyncio
async def test_analyze_stream_sdr(analyzer, mock_ffprobe_sdr, tmp_path):
    """Test stream analysis for SDR content."""
    input_file = tmp_path / "input.mkv"
    input_file.write_bytes(b"test")
    
    with patch('subprocess.check_output') as mock_output:
        mock_output.return_value = mock_ffprobe_sdr.encode()
        info = analyzer.analyze_stream(input_file)
        
    assert info is not None
    assert info.width == 1920
    assert info.height == 1080
    assert info.frame_rate == 24.0
    assert info.pixel_format == 'yuv420p'
    assert info.bit_depth == 8
    assert not info.is_hdr
    assert not info.is_dolby_vision

@pytest.mark.asyncio
async def test_analyze_stream_hdr(analyzer, mock_ffprobe_hdr, tmp_path):
    """Test stream analysis for HDR content."""
    input_file = tmp_path / "input.mkv"
    input_file.write_bytes(b"test")
    
    with patch('subprocess.check_output') as mock_output:
        mock_output.return_value = mock_ffprobe_hdr.encode()
        info = analyzer.analyze_stream(input_file)
        
    assert info is not None
    assert info.width == 3840
    assert info.height == 2160
    assert info.frame_rate == 24.0
    assert info.pixel_format == 'yuv420p10le'
    assert info.bit_depth == 10
    assert info.is_hdr
    assert not info.is_dolby_vision

@pytest.mark.asyncio
async def test_analyze_stream_dolby_vision(analyzer, mock_ffprobe_hdr, tmp_path):
    """Test stream analysis for Dolby Vision content."""
    input_file = tmp_path / "input.mkv"
    input_file.write_bytes(b"test")
    
    with patch('subprocess.check_output') as mock_output:
        def side_effect(cmd, *args, **kwargs):
            if 'mediainfo' in cmd:
                return b'Dolby Vision'
            return mock_ffprobe_hdr.encode()
        mock_output.side_effect = side_effect
        
        info = analyzer.analyze_stream(input_file)
        
    assert info is not None
    assert info.is_hdr
    assert info.is_dolby_vision

def test_get_quality_settings_sd(analyzer):
    """Test quality settings for SD content."""
    info = VideoStreamInfo(
        width=1280,
        height=720,
        is_hdr=False
    )
    crf, pix_fmt = analyzer.get_quality_settings(info)
    assert crf == 25  # Default SD CRF
    assert pix_fmt == 'yuv420p'

def test_get_quality_settings_hd(analyzer):
    """Test quality settings for HD content."""
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=False
    )
    crf, pix_fmt = analyzer.get_quality_settings(info)
    assert crf == 25  # Default HD CRF
    assert pix_fmt == 'yuv420p'

def test_get_quality_settings_uhd_hdr(analyzer):
    """Test quality settings for UHD HDR content."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        is_hdr=True
    )
    crf, pix_fmt = analyzer.get_quality_settings(info)
    assert crf == 29  # Default UHD CRF
    assert pix_fmt == 'yuv420p10le'  # 10-bit for HDR

@pytest.mark.asyncio
async def test_detect_black_bars(analyzer, tmp_path):
    """Test black bar detection."""
    input_file = tmp_path / "input.mkv"
    input_file.write_bytes(b"test")
    
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=False
    )
    
    with patch('subprocess.check_output') as mock_output:
        mock_output.return_value = b'black_level=16'
        crop = analyzer.detect_black_bars(input_file, info)
        
    assert crop is None  # TODO: Implement actual crop detection
