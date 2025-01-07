"""Tests for black bar detection."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from drapto.core.video.types import VideoStreamInfo, CropInfo
from drapto.core.video.cropping import (
    detect_black_bars,
    get_crop_threshold,
    get_credits_skip
)


def test_detect_black_bars(tmp_path):
    """Test black bar detection."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()
    
    with patch('subprocess.run') as mock_run:
        # Mock FFprobe duration query
        mock_run.side_effect = [
            Mock(stdout='{"format": {"duration": "3600"}}'),
            Mock(stderr='''
            [Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:1 t:0.04 crop=1920:800:0:140
            [Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:2 t:0.08 crop=1920:800:0:140
            ''')
        ]
        
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is not None
        assert crop_info.enabled
        assert crop_info.width == 1920
        assert crop_info.height == 800
        assert crop_info.x == 0
        assert crop_info.y == 140


def test_detect_black_bars_no_crop(tmp_path):
    """Test black bar detection with no cropping needed."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()
    
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(stdout='{"format": {"duration": "3600"}}'),
            Mock(stderr='[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:0 y2:1080 w:1920 h:1080 x:0 y:0 pts:1 t:0.04 crop=1920:1080:0:0')
        ]
        
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is not None
        assert not crop_info.enabled


def test_detect_black_bars_error(tmp_path):
    """Test black bar detection with FFmpeg error."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()
    
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = Exception('ffmpeg failed')
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is None


def test_detect_black_bars_no_output(tmp_path):
    """Test black bar detection with no crop output."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    input_path = tmp_path / 'input.mkv'
    input_path.touch()
    
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = [
            Mock(stdout='{"format": {"duration": "3600"}}'),
            Mock(stderr='')  # No crop detection output
        ]
        crop_info = detect_black_bars(input_path, config)
        assert crop_info is None


def test_get_crop_threshold():
    """Test crop threshold selection."""
    # Test SDR threshold
    sdr_info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=False,
        frame_rate=24.0
    )
    assert get_crop_threshold(sdr_info) == 16
    
    # Test HDR threshold
    hdr_info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=True,
        frame_rate=24.0
    )
    assert get_crop_threshold(hdr_info) == 128


def test_get_credits_skip():
    """Test credits skip timing."""
    # Test short content (< 5 minutes)
    assert get_credits_skip(240) == (0, 30)
    
    # Test medium content (5-20 minutes)
    assert get_credits_skip(900) == (15, 30)
    
    # Test TV episode length (20-60 minutes)
    assert get_credits_skip(2400) == (30, 60)
    
    # Test movie length (> 60 minutes)
    assert get_credits_skip(7200) == (60, 180)
    
    # Test very short content
    assert get_credits_skip(10) == (0, 10)


def test_detect_black_bars_sdr():
    """Test black bar detection for SDR content."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    info = VideoStreamInfo(
        width=1920,
        height=1080,
        is_hdr=False,
        frame_rate=24.0
    )
    
    with patch('subprocess.run') as mock_run:
        # Mock duration query
        mock_run.side_effect = [
            Mock(stdout='{"format": {"duration": "3600"}}'),  # ffprobe duration
            Mock(stderr='\n[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:119 t:4.000000 crop=1920:800:0:140\n')  # ffmpeg cropdetect
        ]
        
        crop_info = detect_black_bars(Path('test.mkv'), config, info)
        assert crop_info is not None
        assert crop_info.enabled
        assert crop_info.width == 1920
        assert crop_info.height == 800
        assert crop_info.x == 0
        assert crop_info.y == 140


def test_detect_black_bars_hdr():
    """Test black bar detection for HDR content."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    info = VideoStreamInfo(
        width=3840,
        height=2160,
        is_hdr=True,
        frame_rate=24.0
    )
    
    with patch('subprocess.run') as mock_run:
        # Mock duration query
        mock_run.side_effect = [
            Mock(stdout='{"format": {"duration": "7200"}}'),  # ffprobe duration
            Mock(stderr='\n[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:3840 y1:280 y2:1880 w:3840 h:1600 x:0 y:280 pts:119 t:4.000000 crop=3840:1600:0:280\n')  # ffmpeg cropdetect
        ]
        
        crop_info = detect_black_bars(Path('test.mkv'), config, info)
        assert crop_info is not None
        assert crop_info.enabled
        assert crop_info.width == 3840
        assert crop_info.height == 1600
        assert crop_info.x == 0
        assert crop_info.y == 280


def test_detect_black_bars_error_handling():
    """Test black bar detection error handling."""
    config = {'ffmpeg': 'ffmpeg', 'ffprobe': 'ffprobe'}
    
    with patch('subprocess.run') as mock_run:
        # Test ffprobe failure
        mock_run.side_effect = Exception('ffprobe failed')
        assert detect_black_bars(Path('test.mkv'), config) is None
        
        # Test invalid duration
        mock_run.side_effect = [
            Mock(stdout='{"format": {}}'),  # Missing duration
            Mock(stderr='')
        ]
        assert detect_black_bars(Path('test.mkv'), config) is None
        
        # Test no crop detection
        mock_run.side_effect = [
            Mock(stdout='{"format": {"duration": "3600"}}'),
            Mock(stderr='')  # No crop lines
        ]
        assert detect_black_bars(Path('test.mkv'), config) is None
