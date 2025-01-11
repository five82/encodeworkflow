"""Tests for video analysis types."""

import pytest
from drapto.core.video.types import CropInfo
from drapto.core.video.errors import CropValidationError


def test_crop_info_validation_valid():
    """Test valid crop values."""
    crop = CropInfo(
        x=0,
        y=0,
        width=1920,
        height=1080,
        enabled=True
    )
    # Should not raise any errors
    crop.validate(1920, 1080)


def test_crop_info_validation_larger_width():
    """Test crop width larger than original."""
    crop = CropInfo(
        x=0,
        y=0,
        width=3840,
        height=1080,
        enabled=True
    )
    with pytest.raises(CropValidationError) as exc_info:
        crop.validate(1920, 1080)
    assert "width cannot be larger" in str(exc_info.value)


def test_crop_info_validation_larger_height():
    """Test crop height larger than original."""
    crop = CropInfo(
        x=0,
        y=0,
        width=1920,
        height=2160,
        enabled=True
    )
    with pytest.raises(CropValidationError) as exc_info:
        crop.validate(1920, 1080)
    assert "height cannot be larger" in str(exc_info.value)


def test_crop_info_validation_negative_offset():
    """Test negative crop offsets."""
    crop = CropInfo(
        x=-10,
        y=0,
        width=1920,
        height=1080,
        enabled=True
    )
    with pytest.raises(CropValidationError) as exc_info:
        crop.validate(1920, 1080)
    assert "must be non-negative" in str(exc_info.value)


def test_crop_info_validation_odd_dimensions():
    """Test odd crop dimensions."""
    crop = CropInfo(
        x=0,
        y=0,
        width=1919,  # Odd width, smaller than original
        height=1080,
        enabled=True
    )
    with pytest.raises(CropValidationError) as exc_info:
        crop.validate(1920, 1080)
    assert "must be an even number" in str(exc_info.value)


def test_crop_info_validation_odd_offset():
    """Test odd crop offsets."""
    crop = CropInfo(
        x=1,  # Odd offset
        y=0,
        width=1920,
        height=1080,
        enabled=True
    )
    with pytest.raises(CropValidationError) as exc_info:
        crop.validate(1920, 1080)
    assert "must be an even number" in str(exc_info.value)


def test_crop_info_validation_aspect_ratio():
    """Test aspect ratio validation."""
    crop = CropInfo(
        x=0,
        y=0,
        width=1920,
        height=800,  # Wrong aspect ratio
        enabled=True
    )
    with pytest.raises(CropValidationError) as exc_info:
        crop.validate(1920, 1080)
    assert "aspect ratio" in str(exc_info.value)


def test_crop_info_to_ffmpeg_filter():
    """Test conversion to FFmpeg filter string."""
    crop = CropInfo(
        x=0,
        y=120,
        width=1920,
        height=800,
        enabled=True
    )
    assert crop.to_ffmpeg_filter() == "crop=1920:800:0:120"


def test_crop_info_to_ffmpeg_filter_disabled():
    """Test conversion to FFmpeg filter string when disabled."""
    crop = CropInfo(
        x=0,
        y=120,
        width=1920,
        height=800,
        enabled=False
    )
    assert crop.to_ffmpeg_filter() is None
