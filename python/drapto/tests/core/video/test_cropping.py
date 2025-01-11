"""Tests for black bar detection."""

import json
from pathlib import Path
from unittest.mock import patch, Mock
import subprocess
import ffmpeg

from drapto.core.video.types import VideoStreamInfo, CropInfo
from drapto.core.video.cropping import (
    detect_black_bars,
    _get_black_level,
    get_credits_skip,
    _get_crop_samples
)
from drapto.core.video.errors import BlackBarDetectionError, CropValidationError


def test_get_black_level_sdr(tmp_path):
    """Test black level detection for SDR content."""
    input_path = tmp_path / 'input.mkv'
    input_path.touch()
    
    black_level = _get_black_level(input_path, is_hdr=False)
    assert black_level == 16  # Default SDR black level


@patch('ffmpeg.output')
def test_get_black_level_hdr(mock_output, tmp_path):
    """Test black level detection for HDR content."""
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock the ffmpeg command chain
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_blackdetect_0 @ 0x7f8c] black_level:64\n'
        b'[Parsed_blackdetect_0 @ 0x7f8c] black_level:68\n'
    )

    black_level = _get_black_level(input_path, is_hdr=True)
    assert 99 <= black_level <= 128  # ~1.5x average of sample levels (66 * 1.5 = 99)
    mock_run.assert_called_once()


@patch('ffmpeg.output')
def test_get_black_level_hdr_error(mock_output, tmp_path):
    """Test black level detection with error."""
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock the ffmpeg command chain
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.side_effect = ffmpeg.Error('ffmpeg failed', stdout=b'', stderr=b'error')
    
    black_level = _get_black_level(input_path, is_hdr=True)
    assert black_level == 128  # Default HDR black level on error


def test_get_credits_skip():
    """Test credits skip timing."""
    # Test short content (<5 min)
    assert get_credits_skip(240) == 0.0

    # Test medium content (>5 min, <20 min)
    assert get_credits_skip(900) == 30.0

    # Test longer content (>20 min, <1 hour)
    assert get_credits_skip(2400) == 60.0

    # Test long content (>1 hour)
    assert get_credits_skip(5400) == 180.0


@patch('ffmpeg.output')
def test_get_crop_samples(mock_output, tmp_path):
    """Test crop sample collection."""
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock the ffmpeg command chain
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:1 t:0.04 crop=1920:800:0:140\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:2 t:0.08 crop=1920:800:0:140\n',
    )

    samples = _get_crop_samples(input_path, duration=3600, black_threshold=16,
                              original_width=1920, original_height=1080)
    assert len(samples) == 2
    assert all(w == 1920 and h == 800 for w, h, x, y in samples)
    mock_run.assert_called_once()


@patch('ffmpeg.output')
def test_detect_black_bars_sdr(mock_output, tmp_path):
    """Test black bar detection for SDR content."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=False,
        frame_rate=24.0
    )

    # Mock the ffmpeg command chain
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:1 t:0.04 crop=1920:800:0:140\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:2 t:0.08 crop=1920:800:0:140\n',
    )

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'width': 1920,
            'height': 1080,
            'codec_type': 'video',
            'index': 0,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'filename': 'test.mkv',
            'nb_streams': 1,
            'format_name': 'matroska,webm',
            'duration': '3600.000000'
        }
    }):
        crop_info = detect_black_bars(input_path, config, info)
        assert crop_info is not None
        assert crop_info.enabled
        assert crop_info.width == 1920
        assert crop_info.height == 800
        assert crop_info.x == 0
        assert crop_info.y == 140
    mock_run.assert_called_once()


@patch('ffmpeg.output')
def test_detect_black_bars_hdr(mock_output, tmp_path):
    """Test black bar detection for HDR content."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=True,
        color_transfer='smpte2084',
        frame_rate=24.0
    )

    # First run for black level detection, second for crop detection
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.side_effect = [
        (
            b'',  # stdout
            b'[Parsed_blackdetect_0 @ 0x7f8c] black_level:64\n'
            b'[Parsed_blackdetect_0 @ 0x7f8c] black_level:68\n'
        ),
        (
            b'',  # stdout
            b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:1 t:0.04 crop=1920:800:0:140\n'
            b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:2 t:0.08 crop=1920:800:0:140\n',
        )
    ]

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'width': 1920,
            'height': 1080,
            'codec_type': 'video',
            'index': 0,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'filename': 'test.mkv',
            'nb_streams': 1,
            'format_name': 'matroska,webm',
            'duration': '3600.000000'
        }
    }):
        crop_info = detect_black_bars(input_path, config, info)
        assert crop_info is not None
        assert crop_info.enabled
        assert crop_info.width == 1920
        assert crop_info.height == 800
        assert crop_info.x == 0
        assert crop_info.y == 140
    assert mock_run.call_count == 2


@patch('ffmpeg.output')
def test_detect_black_bars_no_crop(mock_output, tmp_path):
    """Test black bar detection with no cropping needed."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock the ffmpeg command chain
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:0 y2:1080 w:1920 h:1080 x:0 y:0 pts:1 t:0.04 crop=1920:1080:0:0\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:0 y2:1080 w:1920 h:1080 x:0 y:0 pts:2 t:0.08 crop=1920:1080:0:0\n',
    )

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'width': 1920,
            'height': 1080,
            'codec_type': 'video',
            'index': 0,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'filename': 'test.mkv',
            'nb_streams': 1,
            'format_name': 'matroska,webm',
            'duration': '3600.000000'
        }
    }):
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is not None
        assert not crop_info.enabled
    mock_run.assert_called_once()


@patch('ffmpeg.output')
def test_detect_black_bars_invalid_dimensions(mock_output, tmp_path):
    """Test black bar detection with invalid dimensions."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock the ffmpeg command chain
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:1 t:0.04 crop=1920:800:0:140\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:2 t:0.08 crop=1920:800:0:140\n',
    )

    with patch('ffmpeg.probe', side_effect=ffmpeg.Error('Invalid dimensions', stdout=b'', stderr=b'error')):
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is None


@patch('ffmpeg.output')
def test_detect_black_bars_invalid_duration(mock_output, tmp_path):
    """Test black bar detection with invalid duration."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock the ffmpeg command chain
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:1 t:0.04 crop=1920:800:0:140\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:2 t:0.08 crop=1920:800:0:140\n',
    )

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'width': 1920,
            'height': 1080,
            'codec_type': 'video',
            'index': 0,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'filename': 'test.mkv',
            'nb_streams': 1,
            'format_name': 'matroska,webm',
            'duration': '-1.0'
        }
    }):
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is None


@patch('ffmpeg.output')
def test_detect_black_bars_error(mock_output, tmp_path):
    """Test black bar detection with FFmpeg error."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock the ffmpeg command chain
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.side_effect = ffmpeg.Error('FFmpeg failed', stdout=b'', stderr=b'error')

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'width': 1920,
            'height': 1080,
            'codec_type': 'video',
            'index': 0,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'filename': 'test.mkv',
            'nb_streams': 1,
            'format_name': 'matroska,webm',
            'duration': '3600.000000'
        }
    }):
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is None
