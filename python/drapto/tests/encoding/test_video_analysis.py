"""Tests for video analysis functionality."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from drapto.encoding.analysis.video import (
    detect_dolby_vision,
    detect_black_bars,
    detect_black_level,
    detect_hdr,
    VideoAnalysisError,
    HDRDetectionError,
    BlackBarDetectionError,
    FFmpegError,
    MediaInfoError
)
from drapto.encoding.types import VideoStreamInfo, HDRInfo, CropInfo


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for testing."""
    with patch('subprocess.run') as mock_run:
        yield mock_run


@pytest.fixture
def test_video_path(tmp_path):
    """Create a temporary test video file."""
    video_file = tmp_path / "test.mkv"
    video_file.touch()
    return video_file


def test_dolby_vision_detection_success(mock_subprocess, test_video_path):
    """Test successful Dolby Vision detection."""
    mock_subprocess.return_value = MagicMock(
        stdout="Color: Dolby Vision",
        stderr="",
        returncode=0
    )
    
    result = detect_dolby_vision(test_video_path)
    assert result is True
    mock_subprocess.assert_called_once()


def test_dolby_vision_detection_not_found(mock_subprocess, test_video_path):
    """Test when Dolby Vision is not detected."""
    mock_subprocess.return_value = MagicMock(
        stdout="Color: HDR10",
        stderr="",
        returncode=0
    )
    
    result = detect_dolby_vision(test_video_path)
    assert result is False


def test_dolby_vision_detection_mediainfo_error(mock_subprocess, test_video_path):
    """Test MediaInfo command failure."""
    mock_subprocess.side_effect = FileNotFoundError("No mediainfo")
    
    with pytest.raises(MediaInfoError) as exc_info:
        detect_dolby_vision(test_video_path)
    assert "MediaInfo not found" in str(exc_info.value)


def test_dolby_vision_detection_file_not_found():
    """Test when input file does not exist."""
    with pytest.raises(FileNotFoundError) as exc_info:
        detect_dolby_vision(Path("/nonexistent/file.mkv"))
    assert "does not exist" in str(exc_info.value)


def test_black_level_detection_sdr(mock_subprocess, test_video_path):
    """Test black level detection for SDR content."""
    result = detect_black_level(test_video_path, is_hdr=False)
    assert result == 16  # Standard SDR black level
    mock_subprocess.assert_not_called()


def test_black_level_detection_hdr_success(mock_subprocess, test_video_path):
    """Test successful HDR black level detection."""
    mock_subprocess.return_value = MagicMock(
        stderr="[blackdetect] black_level:0.1\n"
              "[blackdetect] black_level:0.15\n"
              "[blackdetect] black_level:0.12",
        returncode=0
    )
    
    result = detect_black_level(test_video_path, is_hdr=True)
    assert 16 <= result <= 256
    mock_subprocess.assert_called_once()


def test_black_level_detection_hdr_no_levels(mock_subprocess, test_video_path):
    """Test HDR black level detection with no levels found."""
    mock_subprocess.return_value = MagicMock(
        stderr="[blackdetect] no levels found",
        returncode=0
    )
    
    result = detect_black_level(test_video_path, is_hdr=True)
    assert result == 128  # Default HDR black level


def test_black_level_detection_error(mock_subprocess, test_video_path):
    """Test black level detection failure."""
    mock_subprocess.side_effect = FFmpegError("FFmpeg failed")
    
    with pytest.raises(HDRDetectionError) as exc_info:
        detect_black_level(test_video_path, is_hdr=True)
    assert "black level detection failed" in str(exc_info.value).lower()


def test_black_bar_detection_success(mock_subprocess, test_video_path):
    """Test successful black bar detection."""
    # Mock duration query
    duration_result = MagicMock(stdout="120.5", returncode=0)
    # Mock crop detection
    crop_result = MagicMock(
        stderr="[Parsed_cropdetect_1] crop=1920:800:0:140",
        returncode=0
    )
    mock_subprocess.side_effect = [duration_result, crop_result]
    
    result = detect_black_bars(test_video_path, {"ffmpeg": "ffmpeg"})
    assert isinstance(result, CropInfo)
    assert result.enabled
    assert result.height == 800
    assert result.y == 140


def test_black_bar_detection_no_bars(mock_subprocess, test_video_path):
    """Test when no black bars are detected."""
    # Mock duration query
    duration_result = MagicMock(stdout="120.5", returncode=0)
    # Mock crop detection with no significant bars
    crop_result = MagicMock(
        stderr="[Parsed_cropdetect_1] crop=1920:1080:0:0",
        returncode=0
    )
    mock_subprocess.side_effect = [duration_result, crop_result]
    
    result = detect_black_bars(test_video_path, {"ffmpeg": "ffmpeg"})
    assert result is None


def test_black_bar_detection_error(mock_subprocess, test_video_path):
    """Test black bar detection failure."""
    mock_subprocess.side_effect = FFmpegError("FFmpeg failed")
    
    with pytest.raises(BlackBarDetectionError) as exc_info:
        detect_black_bars(test_video_path, {"ffmpeg": "ffmpeg"})
    assert "crop detection failed" in str(exc_info.value).lower()


def test_hdr_detection_dolby_vision(mock_subprocess, test_video_path):
    """Test HDR detection with Dolby Vision."""
    mock_subprocess.return_value = MagicMock(
        stdout="Color: Dolby Vision",
        stderr="",
        returncode=0
    )
    
    stream_info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer="smpte2084",
        color_primaries="bt2020",
        color_space="bt2020nc"
    )
    
    result = detect_hdr(stream_info, test_video_path)
    assert isinstance(result, HDRInfo)
    assert result.is_hdr
    assert result.is_dolby_vision
    assert result.hdr_format == "Dolby Vision"


def test_hdr_detection_hdr10(test_video_path):
    """Test HDR10 detection."""
    stream_info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer="smpte2084",
        color_primaries="bt2020",
        color_space="bt2020nc"
    )
    
    result = detect_hdr(stream_info)
    assert isinstance(result, HDRInfo)
    assert result.is_hdr
    assert result.hdr_format == "HDR10"


def test_hdr_detection_hlg(test_video_path):
    """Test HLG detection."""
    stream_info = VideoStreamInfo(
        width=3840,
        height=2160,
        color_transfer="arib-std-b67",
        color_primaries="bt2020",
        color_space="bt2020nc"
    )
    
    result = detect_hdr(stream_info)
    assert isinstance(result, HDRInfo)
    assert result.is_hdr
    assert result.hdr_format == "HLG"


def test_hdr_detection_invalid_input():
    """Test HDR detection with invalid input."""
    with pytest.raises(ValueError) as exc_info:
        detect_hdr(None)
    assert "stream_info cannot be None" in str(exc_info.value)
