"""Tests for HDR detection functionality."""

from pathlib import Path
from unittest.mock import patch, Mock
import subprocess

import pytest

from drapto.core.video.types import VideoStreamInfo, HDRInfo
from drapto.core.video.hdr import detect_hdr, detect_dolby_vision, detect_black_level
from drapto.core.video.errors import HDRDetectionError, BlackBarDetectionError, FFmpegError


def test_detect_dolby_vision():
    """Test Dolby Vision detection."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock mediainfo output with Dolby Vision
        mock_run.return_value = Mock(stdout='Dolby Vision')
        assert detect_dolby_vision(Path('test.mkv')) is True
        
        # Mock mediainfo output without Dolby Vision
        mock_run.return_value = Mock(stdout='HDR10')
        assert detect_dolby_vision(Path('test.mkv')) is False
        
        # Test error handling
        mock_run.side_effect = Exception('mediainfo failed')
        assert detect_dolby_vision(Path('test.mkv')) is False


def test_detect_black_level_sdr():
    """Test black level detection for SDR content."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0)
        assert detect_black_level(Path('test.mkv'), False) == 16


def test_detect_black_level_hdr():
    """Test black level detection for HDR content."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFmpeg output with black levels
        mock_run.return_value = Mock(
            returncode=0,
            stderr='''
            [blackdetect] black_level:100
            [blackdetect] black_level:120
            [blackdetect] black_level:80
            '''
        )
        
        level = detect_black_level(Path('test.mkv'), True)
        assert level > 16  # HDR black level should be higher
        assert level == 100  # Should use average of detected levels


def test_detect_black_level_error():
    """Test black level detection error handling."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffmpeg', stderr='ffmpeg failed')
        with pytest.raises(FFmpegError) as exc_info:
            detect_black_level(Path('test.mkv'), True)
        assert "FFmpeg black level detection failed" in str(exc_info.value)
        assert "ffmpeg failed" in exc_info.value.stderr


def test_detect_hdr_sdr():
    """Test HDR detection with SDR content."""
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        color_transfer='bt709',
        color_primaries='bt709',
        color_space='bt709',
        bit_depth=8
    )

    hdr_info = detect_hdr(info)
    assert hdr_info is None  # SDR content should return None


def test_detect_hdr_hdr10():
    """Test HDR detection with HDR10 content."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='smpte2084',  # PQ
        color_primaries='bt2020',
        color_space='bt2020nc',
        bit_depth=10
    )

    hdr_info = detect_hdr(info)
    assert hdr_info is not None
    assert hdr_info.format == 'hdr10'


def test_detect_hdr_hlg():
    """Test HDR detection with HLG content."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='arib-std-b67',  # HLG
        color_primaries='bt2020',
        color_space='bt2020nc',
        bit_depth=10
    )

    hdr_info = detect_hdr(info)
    assert hdr_info is not None
    assert hdr_info.format == 'hlg'


def test_detect_hdr_dolby_vision():
    """Test HDR detection with Dolby Vision content."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='smpte2084',  # PQ
        color_primaries='bt2020',
        color_space='bt2020nc',
        bit_depth=10,
        input_path=Path('test.mkv')
    )

    with patch('drapto.core.video.hdr.detect_dolby_vision') as mock_detect:
        mock_detect.return_value = True
        hdr_info = detect_hdr(info)
        assert hdr_info is not None
        assert hdr_info.format == 'dolby_vision'


def test_detect_hdr_smpte428():
    """Test HDR detection with SMPTE ST 428 content."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='smpte428',
        color_primaries='xyz',
        color_space='xyz',
        bit_depth=12
    )

    hdr_info = detect_hdr(info)
    assert hdr_info is not None
    assert hdr_info.format == 'smpte428'
