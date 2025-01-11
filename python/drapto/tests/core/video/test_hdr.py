"""Tests for HDR detection functionality."""

from pathlib import Path
from unittest.mock import patch, Mock
import subprocess

import pytest

from drapto.core.video.types import VideoStreamInfo, HDRInfo
from drapto.core.video.hdr import detect_hdr, detect_black_level
from drapto.core.video.errors import HDRDetectionError


def test_detect_black_level_sdr():
    """Test black level detection for SDR content from DVD/Blu-ray."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(returncode=0)
        assert detect_black_level(Path('test.mkv'), False) == 16


def test_detect_black_level_hdr():
    """Test black level detection for HDR content from UHD Blu-ray."""
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
        with pytest.raises(HDRDetectionError) as exc_info:
            detect_black_level(Path('test.mkv'), True)
        assert "Black level detection failed" in str(exc_info.value)


def test_detect_hdr_sdr():
    """Test HDR detection with SDR content from DVD/Blu-ray."""
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        color_transfer='bt709',
        color_primaries='bt709',
        color_space='bt709',
        bit_depth=8,
        input_path=Path('test.mkv')
    )

    hdr_info = detect_hdr(info)
    assert hdr_info is None  # SDR content should return None


def test_detect_hdr_hdr10():
    """Test HDR detection with HDR10 content from UHD Blu-ray."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFmpeg black level detection
        mock_run.return_value = Mock(
            returncode=0,
            stderr='[blackdetect] black_level:100'
        )
        
        info = VideoStreamInfo(
            width=3840,
            height=2160,
            color_transfer='smpte2084',  # PQ
            color_primaries='bt2020',
            color_space='bt2020nc',
            bit_depth=10,
            input_path=Path('test.mkv')
        )

        hdr_info = detect_hdr(info)
        assert hdr_info is not None
        assert hdr_info.format == 'hdr10'
        assert hdr_info.is_hdr is True
        assert hdr_info.is_dolby_vision is False
        assert hdr_info.black_level == 100


def test_detect_hdr_dolby_vision():
    """Test HDR detection with Dolby Vision content from UHD Blu-ray."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFmpeg black level detection
        mock_run.return_value = Mock(
            returncode=0,
            stderr='[blackdetect] black_level:120'
        )
        
        info = VideoStreamInfo(
            width=3840,
            height=2160,
            color_transfer='smpte2084',  # PQ
            color_primaries='bt2020',
            color_space='bt2020nc',
            bit_depth=10,
            input_path=Path('test.mkv'),
            is_dolby_vision=True
        )

        hdr_info = detect_hdr(info)
        assert hdr_info is not None
        assert hdr_info.format == 'dolby_vision'
        assert hdr_info.is_hdr is True
        assert hdr_info.is_dolby_vision is True
        assert hdr_info.black_level == 120


def test_detect_hdr_invalid_dolby_vision():
    """Test HDR detection with invalid Dolby Vision properties."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='bt709',  # Invalid for DV
        color_primaries='bt2020',
        color_space='bt2020nc',
        bit_depth=10,
        input_path=Path('test.mkv'),
        is_dolby_vision=True
    )

    with pytest.raises(HDRDetectionError) as exc_info:
        detect_hdr(info)
    assert "Invalid color properties for Dolby Vision content" in str(exc_info.value)


def test_detect_hdr_invalid_hdr10():
    """Test HDR detection with invalid HDR10 properties."""
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer='bt709',  # Invalid for HDR10
        color_primaries='bt2020',
        color_space='bt2020nc',
        bit_depth=10,
        input_path=Path('test.mkv')
    )

    hdr_info = detect_hdr(info)
    assert hdr_info is None  # Invalid HDR10 properties should return None
