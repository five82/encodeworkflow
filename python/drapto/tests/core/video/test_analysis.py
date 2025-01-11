"""Tests for video stream analysis."""

import json
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from drapto.core.video.types import VideoStreamInfo, HDRInfo, CropInfo
from drapto.core.video.analysis import VideoAnalyzer, StreamAnalysisError


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
            }),
            stderr='',
            returncode=0
        )
        
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
        # Mock FFprobe output with HDR10 properties
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
            }),
            stderr='',
            returncode=0
        )
        
        info = analyzer.analyze_stream(Path('test.mkv'))
        
        assert info is not None
        assert info.width == 3840
        assert info.height == 2160
        assert info.frame_rate == 24.0
        assert info.pixel_format == 'yuv420p10le'
        assert info.bit_depth == 10
        assert info.is_hdr
        assert not info.is_dolby_vision
        assert info.hdr_info is not None
        assert info.hdr_info.format == 'hdr10'


def test_analyze_stream_dolby_vision(analyzer):
    """Test stream analysis with Dolby Vision content."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output with DV properties
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 3840,
                    'height': 2160,
                    'r_frame_rate': '24/1',
                    'pix_fmt': 'yuv420p10le',
                    'color_transfer': 'smpte2084',
                    'color_primaries': 'bt2020',
                    'color_space': 'bt2020nc',
                    'side_data_list': [{'dv_profile': 5}]  # Add DV profile to indicate Dolby Vision
                }]
            }),
            stderr='',
            returncode=0
        )
        
        info = analyzer.analyze_stream(Path('test.mkv'))
        
        assert info is not None
        assert info.width == 3840
        assert info.height == 2160
        assert info.frame_rate == 24.0
        assert info.pixel_format == 'yuv420p10le'
        assert info.bit_depth == 10
        assert info.is_hdr
        assert info.is_dolby_vision
        assert info.hdr_info is not None
        assert info.hdr_info.format == 'dolby_vision'


def test_analyze_stream_with_crop(analyzer):
    """Test stream analysis with crop detection."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run, \
         patch('ffmpeg.probe') as mock_probe, \
         patch('ffmpeg.output') as mock_output:
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
        mock_run.side_effect = [stream_info_mock, duration_mock]

        # Mock ffmpeg.probe calls in detect_black_bars
        mock_probe.return_value = {
            'streams': [{
                'codec_type': 'video',
                'width': 1920,
                'height': 1080,
                'r_frame_rate': '24/1'
            }],
            'format': {
                'duration': '3600.000000'
            }
        }

        # Mock ffmpeg.output for crop detection
        mock_output.return_value.overwrite_output.return_value.run.return_value = (
            b'',  # stdout
            b'[Parsed_cropdetect_0 @ 0x7f8c] x1:0 x2:1920 y1:140 y2:940 w:1920 h:800 x:0 y:140 pts:119 t:4.000000 crop=1920:800:0:140'
        )

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
        mock_run.return_value = Mock(
            stdout=json.dumps({'streams': []}),
            stderr='',
            returncode=0
        )
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(Path('test.mkv'))
        assert "No video streams found" in str(exc_info.value)

        # Test invalid JSON
        mock_run.return_value = Mock(
            stdout='invalid json',
            stderr='',
            returncode=0
        )
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(Path('test.mkv'))
        assert "Failed to parse FFprobe output" in str(exc_info.value)


def test_analyze_stream_error(analyzer):
    """Test analyzing stream with FFmpeg error."""
    input_path = Path('test.mp4')
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, [], stderr="FFmpeg error")
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(input_path)
        assert "FFprobe command failed" in str(exc_info.value)
        assert "FFmpeg error" in str(exc_info.value)


def test_analyze_stream_invalid_json(analyzer):
    """Test analyzing stream with invalid JSON."""
    input_path = Path('test.mp4')
    
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            stdout='invalid json',
            stderr='',
            returncode=0
        )
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(input_path)
        assert "Failed to parse FFprobe output" in str(exc_info.value)


def test_analyze_stream_invalid_width(analyzer):
    """Test stream analysis with invalid width."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output with invalid width
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 8,  # Too small
                    'height': 1080,
                    'r_frame_rate': '24/1',
                    'pix_fmt': 'yuv420p'
                }]
            }),
            stderr='',
            returncode=0
        )
        
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(Path('test.mkv'))
        assert "Invalid video width" in str(exc_info.value)


def test_analyze_stream_invalid_height(analyzer):
    """Test stream analysis with invalid height."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output with invalid height
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 1920,
                    'height': 10000,  # Too large
                    'r_frame_rate': '24/1',
                    'pix_fmt': 'yuv420p'
                }]
            }),
            stderr='',
            returncode=0
        )
        
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(Path('test.mkv'))
        assert "Invalid video height" in str(exc_info.value)


def test_analyze_stream_invalid_frame_rate(analyzer):
    """Test stream analysis with invalid frame rate."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output with invalid frame rate
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 1920,
                    'height': 1080,
                    'r_frame_rate': '1/2',  # 0.5 fps is too low
                    'pix_fmt': 'yuv420p'
                }]
            }),
            stderr='',
            returncode=0
        )
        
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(Path('test.mkv'))
        assert "Invalid frame rate" in str(exc_info.value)


def test_analyze_stream_invalid_bit_depth(analyzer):
    """Test stream analysis with invalid bit depth."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output with invalid pixel format
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 1920,
                    'height': 1080,
                    'r_frame_rate': '24/1',
                    'pix_fmt': 'yuv420p16le'  # 16-bit not supported
                }]
            }),
            stderr='',
            returncode=0
        )
        
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(Path('test.mkv'))
        assert "Invalid bit depth" in str(exc_info.value)


def test_analyze_stream_unexpected_color_properties(analyzer, caplog):
    """Test stream analysis with unexpected color properties."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe output with unexpected color properties
        mock_run.return_value = Mock(
            stdout=json.dumps({
                'streams': [{
                    'width': 1920,
                    'height': 1080,
                    'r_frame_rate': '24/1',
                    'pix_fmt': 'yuv420p',
                    'color_space': 'unknown_space',
                    'color_transfer': 'unknown_transfer',
                    'color_primaries': 'unknown_primaries'
                }]
            }),
            stderr='',
            returncode=0
        )
        
        info = analyzer.analyze_stream(Path('test.mkv'))
        
        # Should warn but not fail
        assert info is not None
        assert "Unexpected color space" in caplog.text
        assert "Unexpected color transfer" in caplog.text
        assert "Unexpected color primaries" in caplog.text


def test_analyze_stream_missing_file(analyzer):
    """Test stream analysis with missing input file."""
    with patch('pathlib.Path.exists', return_value=False):
        with pytest.raises(FileNotFoundError) as exc_info:
            analyzer.analyze_stream(Path('nonexistent.mkv'))
        assert "Input file does not exist" in str(exc_info.value)


def test_analyze_stream_ffprobe_error(analyzer):
    """Test stream analysis with FFprobe error."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('subprocess.run') as mock_run:
        # Mock FFprobe error
        mock_run.return_value = Mock(
            returncode=1,
            stderr="FFprobe error"
        )
        
        with pytest.raises(StreamAnalysisError) as exc_info:
            analyzer.analyze_stream(Path('test.mkv'))
        assert "FFprobe analysis failed" in str(exc_info.value)
        assert "FFprobe error" in str(exc_info.value)
