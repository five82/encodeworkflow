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


@patch('ffmpeg.output')
def test_detect_black_bars_error(mock_output, tmp_path):
    """Test error handling in black bar detection."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    with patch('ffmpeg.probe', side_effect=ffmpeg.Error('Invalid dimensions', stdout=b'', stderr=b'error')):
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is None


@patch('ffmpeg.output')
def test_invalid_crop_samples(mock_output, tmp_path):
    """Test handling of invalid crop samples."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock the ffmpeg command chain with some invalid samples
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:1 t:0.04 crop=1920:800:0:140\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:0 y2:1080 w:2000 h:1200 x:0 y:0 pts:2 t:0.08 crop=2000:1200:0:0\n'  # Invalid - dimensions too large
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:3 t:0.12 crop=1920:800:0:140\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] Invalid crop line\n'  # Invalid format
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:-800 x:0 y:140 pts:4 t:0.16 crop=1920:-800:0:140\n'  # Invalid - negative height
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
        assert crop_info.enabled
        assert crop_info.width == 1920
        assert crop_info.height == 800
        assert crop_info.x == 0
        assert crop_info.y == 140


@patch('ffmpeg.output')
def test_black_level_detection_hdr(mock_output, tmp_path):
    """Test black level detection for HDR content with various levels."""
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock black level detection with multiple values
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_blackdetect_0 @ 0x7f8c] black_level:64\n'
        b'[Parsed_blackdetect_0 @ 0x7f8c] black_level:68\n'
        b'[Parsed_blackdetect_0 @ 0x7f8c] black_level:72\n'
        b'[Parsed_blackdetect_0 @ 0x7f8c] Invalid black level line\n'  # Invalid format
        b'[Parsed_blackdetect_0 @ 0x7f8c] black_level:70\n'
    )

    level = _get_black_level(input_path, is_hdr=True)
    assert level == int(68.5 * 1.5)  # Average of [64, 68, 72, 70] * 1.5


@patch('ffmpeg.output')
def test_black_level_detection_error(mock_output, tmp_path):
    """Test black level detection error handling."""
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock FFmpeg error with stderr
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.side_effect = ffmpeg.Error('FFmpeg error', stdout=b'', stderr=b'Some FFmpeg error occurred')

    # Should fall back to default HDR black level
    level = _get_black_level(input_path, is_hdr=True)
    assert level == 128


@patch('loguru.logger.debug')
@patch('loguru.logger.info')
@patch('loguru.logger.warning')
@patch('loguru.logger.error')
def test_logging_behavior(mock_error, mock_warning, mock_info, mock_debug, tmp_path):
    """Test that appropriate logging occurs during black bar detection."""
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    with patch('ffmpeg.probe', side_effect=ffmpeg.Error('FFmpeg error', stdout=b'', stderr=b'Some FFmpeg error')):
        detect_black_bars(input_path, {})
        
    # Verify error was logged
    mock_error.assert_called_with(
        'FFmpeg error during black bar detection: Some FFmpeg error'
    )

    # Test non-existent file
    non_existent = tmp_path / 'nonexistent.mkv'
    detect_black_bars(non_existent, {})
    mock_error.assert_called_with(
        f'Input file does not exist: {non_existent}'
    )


@patch('ffmpeg.output')
def test_detect_black_bars_short_video(mock_output, tmp_path):
    """Test black bar detection for very short videos."""
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
    )

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'codec_type': 'video',
            'width': 1920,
            'height': 1080,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'duration': '120.000000'  # 2 minutes
        }
    }):
        crop_info = detect_black_bars(input_path, config, info)
        assert crop_info is not None
        assert crop_info.enabled
        assert crop_info.width == 1920
        assert crop_info.height == 800


@patch('ffmpeg.output')
def test_detect_black_bars_mixed_samples(mock_output, tmp_path):
    """Test black bar detection with inconsistent crop samples."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=False,
        frame_rate=24.0
    )

    # Mock the ffmpeg command chain with different crop values
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:1 t:0.04 crop=1920:800:0:140\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:130 y2:950 w:1920 h:820 x:0 y:130 pts:2 t:0.08 crop=1920:820:0:130\n'
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:3 t:0.12 crop=1920:800:0:140\n'
    )

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'codec_type': 'video',
            'width': 1920,
            'height': 1080,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'duration': '3600.000000'
        }
    }):
        crop_info = detect_black_bars(input_path, config, info)
        assert crop_info is not None
        assert crop_info.enabled
        # Should use most common values
        assert crop_info.width == 1920
        assert crop_info.height == 800
        assert crop_info.x == 0
        assert crop_info.y == 140


@patch('ffmpeg.output')
def test_detect_black_bars_near_original(mock_output, tmp_path):
    """Test black bar detection with crop values very close to original dimensions."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=False,
        frame_rate=24.0
    )

    # Mock the ffmpeg command chain with crop values close to original
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.return_value = (
        b'',  # stdout
        b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:2 y2:1074 w:1920 h:1072 x:0 y:2 pts:1 t:0.04 crop=1920:1072:0:2\n'
    )

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'codec_type': 'video',
            'width': 1920,
            'height': 1080,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'duration': '3600.000000'
        }
    }):
        crop_info = detect_black_bars(input_path, config, info)
        assert crop_info is not None
        # Should not crop when difference is less than MIN_CROP_PIXELS (10)
        assert not crop_info.enabled


@patch('ffmpeg.output')
def test_detect_black_bars_permission_error(mock_output, tmp_path):
    """Test black bar detection with file permission error."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()
    
    # Mock permission error
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.side_effect = ffmpeg.Error('Permission denied', stdout=b'', stderr=b'Permission denied')

    with patch('ffmpeg.probe', side_effect=ffmpeg.Error('Permission denied', stdout=b'', stderr=b'Permission denied')):
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is None


@patch('ffmpeg.output')
def test_detect_black_bars_memory_error(mock_output, tmp_path):
    """Test black bar detection with memory allocation error."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Mock memory error
    mock_run = mock_output.return_value.overwrite_output.return_value.run
    mock_run.side_effect = ffmpeg.Error('Cannot allocate memory', stdout=b'', stderr=b'Cannot allocate memory')

    with patch('ffmpeg.probe', return_value={
        'streams': [{
            'codec_type': 'video',
            'width': 1920,
            'height': 1080,
            'r_frame_rate': '24/1'
        }],
        'format': {
            'duration': '3600.000000'
        }
    }):
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is None


def test_detect_black_bars_invalid_stream_info(tmp_path):
    """Test black bar detection with invalid video stream info."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()

    # Test with invalid width
    info = VideoStreamInfo(
        width=-1920,  # Invalid width
        height=1080,
        is_hdr=False,
        frame_rate=24.0
    )
    crop_info = detect_black_bars(input_path, config, info)
    assert crop_info is None

    # Test with invalid height
    info = VideoStreamInfo(
        width=1920,
        height=-1080,  # Invalid height
        is_hdr=False,
        frame_rate=24.0
    )
    crop_info = detect_black_bars(input_path, config, info)
    assert crop_info is None

    # Test with invalid frame rate
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=False,
        frame_rate=-24.0  # Invalid frame rate
    )
    crop_info = detect_black_bars(input_path, config, info)
    assert crop_info is None
