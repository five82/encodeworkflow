"""Tests for video stream analysis."""

import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from drapto.core.video.types import VideoStreamInfo, HDRInfo, CropInfo
from drapto.core.video.analysis import VideoAnalyzer


@pytest.fixture
def config():
    """Test configuration."""
    return {
        'ffmpeg': 'ffmpeg',
        'ffprobe': 'ffprobe'
    }


@pytest.fixture
def analyzer(config):
    """Test analyzer instance."""
    return VideoAnalyzer(config)


def test_analyze_stream_sdr(analyzer):
    """Test stream analysis with SDR content."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 1920,
                    'height': 1080,
                    'r_frame_rate': '24000/1001',
                    'pix_fmt': 'yuv420p',
                    'color_transfer': 'bt709',
                    'color_primaries': 'bt709',
                    'color_space': 'bt709'
                }]
            })
        )
        
        with patch('drapto.core.video.hdr.detect_dolby_vision', return_value=False):
            info = analyzer.analyze_stream(Path('test.mkv'))
            
            assert info is not None
            assert info.width == 1920
            assert info.height == 1080
            assert info.frame_rate == 23.976023976023978
            assert info.pixel_format == 'yuv420p'
            assert info.bit_depth == 8
            assert not info.is_hdr
            assert not info.is_dolby_vision


def test_analyze_stream_hdr10(analyzer):
    """Test stream analysis with HDR10 content."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 3840,
                    'height': 2160,
                    'r_frame_rate': '24/1',
                    'pix_fmt': 'yuv420p10le',
                    'color_transfer': 'smpte2084',
                    'color_primaries': 'bt2020',
                    'color_space': 'bt2020nc'
                }]
            })
        )
        
        with patch('drapto.core.video.hdr.detect_dolby_vision', return_value=False):
            info = analyzer.analyze_stream(Path('test.mkv'))
            
            assert info is not None
            assert info.width == 3840
            assert info.height == 2160
            assert info.frame_rate == 24.0
            assert info.pixel_format == 'yuv420p10le'
            assert info.bit_depth == 10
            assert info.is_hdr
            assert not info.is_dolby_vision


def test_analyze_stream_dolby_vision(analyzer):
    """Test stream analysis with Dolby Vision content."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 3840,
                    'height': 2160,
                    'r_frame_rate': '24/1',
                    'pix_fmt': 'yuv420p10le',
                    'color_transfer': 'smpte2084',
                    'color_primaries': 'bt2020',
                    'color_space': 'bt2020nc'
                }]
            })
        )
        
        with patch('drapto.core.video.hdr.detect_dolby_vision', return_value=True):
            info = analyzer.analyze_stream(Path('test.mkv'))
            
            assert info is not None
            assert info.width == 3840
            assert info.height == 2160
            assert info.frame_rate == 24.0
            assert info.pixel_format == 'yuv420p10le'
            assert info.bit_depth == 10
            assert info.is_hdr
            assert info.is_dolby_vision


def test_analyze_stream_with_crop(analyzer):
    """Test stream analysis with crop detection."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output for stream info
        stream_info_mock = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 1920,
                    'height': 1080,
                    'r_frame_rate': '24/1',
                    'pix_fmt': 'yuv420p'
                }]
            }),
            stderr='',
            returncode=0
        )
        
        # Mock FFprobe duration query
        duration_mock = Mock(
            stdout=json.dumps({
                'format': {
                    'duration': '3600'
                }
            }),
            stderr='',
            returncode=0
        )
        
        # Mock FFmpeg crop detection
        crop_mock = Mock(
            stdout='',
            stderr='''[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:119 t:4.000000 crop=1920:800:0:140''',
            returncode=0
        )
        
        mock_run.side_effect = [stream_info_mock, duration_mock, crop_mock]
        
        # Mock HDR detection to return False
        with patch('drapto.core.video.hdr.detect_dolby_vision', return_value=False):
            info = analyzer.analyze_stream(Path('test.mkv'))
            assert info is not None
            assert info.crop_info is not None
            assert info.crop_info.enabled
            assert info.crop_info.width == 1920
            assert info.crop_info.height == 800
            assert info.crop_info.x == 0
            assert info.crop_info.y == 140


def test_analyze_stream_error_handling(analyzer):
    """Test stream analysis error handling."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Test missing streams
        mock_run.return_value = Mock(stdout='{"streams": []}')
        assert analyzer.analyze_stream(Path('test.mkv')) is None
        
        # Test invalid JSON
        mock_run.return_value = Mock(stdout='invalid json')
        assert analyzer.analyze_stream(Path('test.mkv')) is None
        
        # Test FFprobe failure
        mock_run.side_effect = Exception('ffprobe failed')
        assert analyzer.analyze_stream(Path('test.mkv')) is None


def test_analyze_stream_error(analyzer):
    """Test analyzing stream with FFmpeg error."""
    input_path = Path('test.mp4')
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, [])
        assert analyzer.analyze_stream(input_path) is None


def test_analyze_stream_invalid_json(analyzer):
    """Test analyzing stream with invalid JSON."""
    input_path = Path('test.mp4')
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(stdout='invalid json')
        assert analyzer.analyze_stream(input_path) is None
