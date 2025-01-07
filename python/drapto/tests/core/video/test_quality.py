"""Tests for quality settings."""

import pytest
from unittest.mock import Mock
from drapto.core.video.types import VideoStreamInfo, QualitySettings
from drapto.core.video.quality import get_quality_settings, validate_preset


def test_validate_preset():
    """Test SVT-AV1 preset validation."""
    # Test all valid presets (0-13)
    for preset in range(14):
        assert validate_preset(preset) == preset
    
    # Test clamping
    assert validate_preset(-1) == 0  # Below minimum
    assert validate_preset(14) == 13  # Above maximum
    assert validate_preset(100) == 13  # Well above maximum
    assert validate_preset(-100) == 0  # Well below minimum
    
    # Test invalid types
    assert validate_preset("medium") == 6  # String preset
    assert validate_preset(None) == 6  # None value
    assert validate_preset(3.14) == 6  # Float value


def test_get_quality_settings_sd():
    """Test quality settings for SD content."""
    stream_info = VideoStreamInfo(
        width=1280,
        height=720,
        frame_rate=24.0,
        is_hdr=False
    )
    
    settings = get_quality_settings(stream_info)
    assert settings.crf == 25  # SD CRF
    assert settings.preset == 6  # Default preset
    assert settings.max_bitrate == 4_000_000  # 4 Mbps for SD
    assert settings.bufsize == 8_000_000  # 8 Mbps buffer
    assert settings.svt_params == "tune=0:film-grain=0:film-grain-denoise=0"


def test_get_quality_settings_hd():
    """Test quality settings for HD content."""
    stream_info = VideoStreamInfo(
        width=1920,
        height=1080,
        frame_rate=24.0,
        is_hdr=False
    )
    
    settings = get_quality_settings(stream_info)
    assert settings.crf == 25  # HD CRF
    assert settings.preset == 6  # Default preset
    assert settings.max_bitrate == 8_000_000  # 8 Mbps for HD
    assert settings.bufsize == 16_000_000  # 16 Mbps buffer


def test_get_quality_settings_uhd():
    """Test quality settings for UHD content."""
    stream_info = VideoStreamInfo(
        width=3840,
        height=2160,
        frame_rate=24.0,
        is_hdr=False
    )
    
    settings = get_quality_settings(stream_info)
    assert settings.crf == 29  # UHD CRF
    assert settings.preset == 6  # Default preset
    assert settings.max_bitrate == 16_000_000  # 16 Mbps for UHD
    assert settings.bufsize == 32_000_000  # 32 Mbps buffer


def test_get_quality_settings_high_fps():
    """Test quality settings for high frame rate content."""
    stream_info = VideoStreamInfo(
        width=1920,
        height=1080,
        frame_rate=60.0,
        is_hdr=False
    )
    
    settings = get_quality_settings(stream_info)
    assert settings.crf == 25  # HD CRF
    assert settings.preset == 6  # Default preset
    assert settings.max_bitrate == 12_000_000  # 8 Mbps * 1.5 for high fps
    assert settings.bufsize == 24_000_000  # 16 Mbps * 1.5 for high fps


def test_get_quality_settings_error():
    """Test quality settings with invalid input."""
    stream_info = None
    
    settings = get_quality_settings(stream_info)
    assert settings.crf == 25  # Default CRF
    assert settings.preset == 6  # Default preset
