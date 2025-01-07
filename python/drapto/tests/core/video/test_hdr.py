"""Tests for HDR detection."""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from drapto.core.video.types import VideoStreamInfo, HDRInfo
from drapto.core.video.hdr import detect_hdr, detect_dolby_vision, detect_black_level


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


def test_detect_black_level_sdr():
    """Test black level detection for SDR content."""
    assert detect_black_level(Path('test.mkv'), is_hdr=False) == 16


def test_detect_black_level_hdr_success():
    """Test successful black level detection for HDR content."""
    with patch('subprocess.run') as mock_run:
        # Mock FFmpeg output with black levels
        mock_run.return_value = Mock(
            stderr='''
            [blackdetect] black_level:0.1
            [blackdetect] black_level:0.12
            [blackdetect] black_level:0.08
            '''
        )
        level = detect_black_level(Path('test.mkv'), is_hdr=True)
        assert level == 16  # (0.1 average * 1.5) clamped to minimum 16


def test_detect_black_level_hdr_high():
    """Test black level detection with high values."""
    with patch('subprocess.run') as mock_run:
        # Mock FFmpeg output with high black levels
        mock_run.return_value = Mock(
            stderr='''
            [blackdetect] black_level:200
            [blackdetect] black_level:180
            [blackdetect] black_level:220
            '''
        )
        level = detect_black_level(Path('test.mkv'), is_hdr=True)
        assert level == 256  # (200 average * 1.5) clamped to maximum 256


def test_detect_black_level_hdr_error():
    """Test black level detection error handling."""
    with patch('subprocess.run') as mock_run:
        # Test FFmpeg failure
        mock_run.side_effect = Exception('FFmpeg failed')
        assert detect_black_level(Path('test.mkv'), is_hdr=True) == 128
        
        # Test invalid output format
        mock_run.side_effect = None
        mock_run.return_value = Mock(stderr='Invalid output')
        assert detect_black_level(Path('test.mkv'), is_hdr=True) == 128


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
    assert not hdr_info.is_dolby_vision
    assert hdr_info.hdr_format == 'HDR10'


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
    assert not hdr_info.is_dolby_vision
    assert hdr_info.hdr_format == 'HLG'


def test_detect_hdr_smpte428():
    """Test SMPTE ST.428 detection."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='smpte428',
        color_primaries='bt2020',
        color_space='bt2020nc',
        pixel_format='yuv420p12le',
        frame_rate=24.0,
        bit_depth=12
    )
    
    hdr_info = detect_hdr(info)
    assert hdr_info.is_hdr
    assert not hdr_info.is_dolby_vision
    assert hdr_info.hdr_format == 'HDR'


def test_detect_hdr_bt2020():
    """Test BT.2020 detection."""
    for transfer in ['bt2020-10', 'bt2020-12']:
        info = VideoStreamInfo(
            width=3840,
            height=2160,
            color_transfer=transfer,
            color_primaries='bt2020',
            color_space='bt2020nc',
            pixel_format='yuv420p10le',
            frame_rate=24.0,
            bit_depth=10
        )
        
        hdr_info = detect_hdr(info)
        assert hdr_info.is_hdr
        assert not hdr_info.is_dolby_vision
        assert hdr_info.hdr_format == 'HDR'


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
    # Test with only color primaries
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer=None,
        color_primaries='bt2020',
        color_space=None,
        pixel_format='yuv420p10le',
        frame_rate=24.0,
        bit_depth=10
    )
    
    hdr_info = detect_hdr(info)
    assert hdr_info.is_hdr
    assert hdr_info.hdr_format == 'HDR'
    
    # Test with only color space
    info.color_primaries = None
    info.color_space = 'bt2020nc'
    
    hdr_info = detect_hdr(info)
    assert hdr_info.is_hdr
    assert hdr_info.hdr_format == 'HDR'
    
    # Test with mixed SDR/HDR indicators
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='bt709',
        color_primaries='bt2020',  # HDR
        color_space='bt709',
        pixel_format='yuv420p10le',
        frame_rate=24.0,
        bit_depth=10
    )
    
    hdr_info = detect_hdr(info)
    assert hdr_info.is_hdr
    assert hdr_info.hdr_format == 'HDR'
