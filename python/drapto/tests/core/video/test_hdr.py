"""Tests for HDR detection."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from drapto.core.video.types import VideoStreamInfo, HDRInfo
from drapto.core.video.hdr import detect_hdr, detect_dolby_vision


def test_detect_dolby_vision():
    """Test Dolby Vision detection."""
    with patch('subprocess.run') as mock_run:
        # Mock mediainfo output with Dolby Vision
        mock_run.return_value = Mock(stdout='Dolby Vision, Version 1.0')
        assert detect_dolby_vision(Path('test.mkv')) is True
        
        # Mock mediainfo output without Dolby Vision
        mock_run.return_value = Mock(stdout='HDR10')
        assert detect_dolby_vision(Path('test.mkv')) is False
        
        # Test error handling
        mock_run.side_effect = Exception('mediainfo failed')
        assert detect_dolby_vision(Path('test.mkv')) is False


def test_detect_hdr_sdr():
    """Test SDR detection."""
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        color_transfer='bt709',
        color_primaries='bt709',
        color_space='bt709',
        pixel_format='yuv420p',
        frame_rate=24.0,
        bit_depth=8
    )
    
    hdr_info = detect_hdr(info)
    assert not hdr_info.is_hdr
    assert not hdr_info.is_dolby_vision
    assert hdr_info.hdr_format is None


def test_detect_hdr_hdr10():
    """Test HDR10 detection."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='smpte2084',  # PQ
        color_primaries='bt2020',
        color_space='bt2020nc',
        pixel_format='yuv420p10le',
        frame_rate=24.0,
        bit_depth=10
    )
    
    hdr_info = detect_hdr(info)
    assert hdr_info.is_hdr
    assert hdr_info.hdr_format == 'HDR10'
    assert not hdr_info.is_dolby_vision


def test_detect_hdr_hlg():
    """Test HLG detection."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='arib-std-b67',  # HLG
        color_primaries='bt2020',
        color_space='bt2020nc',
        pixel_format='yuv420p10le',
        frame_rate=24.0,
        bit_depth=10
    )
    
    hdr_info = detect_hdr(info)
    assert hdr_info.is_hdr
    assert hdr_info.hdr_format == 'HLG'
    assert not hdr_info.is_dolby_vision


def test_detect_hdr_dolby_vision():
    """Test Dolby Vision detection."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='smpte2084',
        color_primaries='bt2020',
        color_space='bt2020nc',
        pixel_format='yuv420p10le',
        frame_rate=24.0,
        bit_depth=10
    )
    
    with patch('drapto.core.video.hdr.detect_dolby_vision') as mock_detect:
        mock_detect.return_value = True
        hdr_info = detect_hdr(info, Path('test.mkv'))
        assert hdr_info.is_hdr
        assert hdr_info.is_dolby_vision
        assert hdr_info.hdr_format == 'Dolby Vision'


def test_detect_hdr_edge_cases():
    """Test HDR detection edge cases."""
    # Test with missing color info
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        frame_rate=24.0
    )
    hdr_info = detect_hdr(info)
    assert not hdr_info.is_hdr
    
    # Test with high bit depth but no HDR transfer
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        color_transfer='bt709',
        pixel_format='yuv420p10le',
        bit_depth=10,
        frame_rate=24.0
    )
    hdr_info = detect_hdr(info)
    assert hdr_info.is_hdr  # High bit depth indicates HDR
    
    # Test with BT.2020 color space but no HDR transfer
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        color_space='bt2020nc',
        frame_rate=24.0
    )
    hdr_info = detect_hdr(info)
    assert hdr_info.is_hdr  # BT.2020 indicates HDR


def test_detect_hdr_error():
    """Test HDR detection with invalid data."""
    stream_info = VideoStreamInfo(
        width=1920,
        height=1080,
        color_transfer=None,
        color_primaries=None,
        color_space=None
    )
    
    hdr_info = detect_hdr(stream_info)
    assert not hdr_info.is_hdr
    assert not hdr_info.is_dolby_vision
    assert hdr_info.hdr_format is None
