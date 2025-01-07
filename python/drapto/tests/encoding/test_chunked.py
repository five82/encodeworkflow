"""Tests for the chunked encoding path."""

import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from drapto.core.base import EncodingContext
from drapto.encoding.chunked import ChunkedEncoder
from drapto.core.video.analysis import VideoAnalyzer, VideoStreamInfo

@pytest.fixture
def config():
    return {
        'ffmpeg': 'ffmpeg',
        'ffprobe': 'ffprobe',
        'segment_length': 10,
        'vmaf_target': 95,
        'vmaf_samples': 4,
        'vmaf_duration': '1s'
    }

@pytest.fixture
def encoder(config):
    return ChunkedEncoder(config)

@pytest.fixture
def context():
    return EncodingContext(
        input_path=Path('/path/to/input.mkv'),
        output_path=Path('/path/to/output.mkv'),
        target_vmaf=95.0,
        preset=10,
        svt_params='tune=0:film-grain=0'
    )

@pytest.fixture
def mock_stream_info():
    return Mock(
        width=3840,
        height=2160,
        is_hdr=True,
        is_dolby_vision=False,
        frame_rate=24
    )

@pytest.fixture
def mock_ffprobe_output():
    return {
        'streams': [{
            'codec_type': 'video',
            'width': 3840,
            'height': 2160,
            'r_frame_rate': '24/1',
            'color_space': 'bt2020nc',
            'color_transfer': 'smpte2084',
            'color_primaries': 'bt2020'
        }]
    }

@pytest.mark.asyncio
async def test_encode_content_dolby_vision(encoder, context, mock_stream_info):
    """Should reject Dolby Vision content."""
    mock_stream_info.is_dolby_vision = True
    with patch('drapto.encoding.chunked.VideoAnalyzer') as mock_analyzer:
        mock_analyzer.return_value.analyze_stream.return_value = mock_stream_info
        result = await encoder.encode_content(context)
        assert not result

@pytest.mark.asyncio
async def test_segment_video(encoder, context):
    """Should successfully segment video."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / 'segments'
        output_dir.mkdir()
        
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            result = await encoder._segment_video(context.input_path, output_dir)
            assert result
            mock_exec.assert_called_once()
            cmd = mock_exec.call_args[0]
            assert cmd[0] == 'ffmpeg'
            assert '-segment_time' in cmd
            assert str(encoder._segment_length) in cmd

@pytest.mark.asyncio
async def test_validate_segments(encoder):
    """Should validate segments correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        segments_dir = Path(temp_dir)
        
        # Create test segments
        for i in range(3):
            segment = segments_dir / f'{i:04d}.mkv'
            segment.write_bytes(b'x' * 2048)  # 2KB file
            
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            result = await encoder._validate_segments(segments_dir)
            assert result
            assert mock_exec.call_count == 3

@pytest.mark.asyncio
async def test_validate_segments_invalid(encoder):
    """Should detect invalid segments."""
    with tempfile.TemporaryDirectory() as temp_dir:
        segments_dir = Path(temp_dir)
        
        # Create invalid segment (too small)
        segment = segments_dir / '0000.mkv'
        segment.write_bytes(b'x' * 512)  # 512B file
        
        result = await encoder._validate_segments(segments_dir)
        assert not result

@pytest.mark.asyncio
async def test_encode_segments(encoder, context):
    """Should encode segments in parallel."""
    with tempfile.TemporaryDirectory() as temp_dir:
        input_dir = Path(temp_dir) / 'input'
        output_dir = Path(temp_dir) / 'output'
        input_dir.mkdir()
        output_dir.mkdir()
        
        # Create test segments
        for i in range(3):
            segment = input_dir / f'{i:04d}.mkv'
            segment.write_bytes(b'x' * 2048)
            
        # Mock shutil.which to simulate GNU Parallel installed
        with patch('shutil.which', return_value='/usr/bin/parallel'):
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b'', b'')
            mock_process.returncode = 0
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
                result = await encoder._encode_segments(input_dir, output_dir, context, 30, 'yuv420p10le')
                assert result
                
                # Verify parallel command was called correctly
                assert mock_exec.call_count > 0
                args = mock_exec.call_args[0]
                
                # Check key arguments
                assert '/usr/bin/parallel' in args
                assert '--will-cite' in args
                assert str(input_dir / '*.mkv') in args

@pytest.mark.asyncio
async def test_encode_segments_no_parallel(encoder, context):
    """Should fail if GNU Parallel not installed."""
    with tempfile.TemporaryDirectory() as temp_dir:
        input_dir = Path(temp_dir) / 'input'
        output_dir = Path(temp_dir) / 'output'
        input_dir.mkdir()
        output_dir.mkdir()
        
        # Mock shutil.which to simulate GNU Parallel not installed
        with patch('shutil.which', return_value=None):
            result = await encoder._encode_segments(input_dir, output_dir, context, 30, 'yuv420p10le')
            assert not result

@pytest.mark.asyncio
async def test_concatenate_segments(encoder, context):
    """Should concatenate segments successfully."""
    with tempfile.TemporaryDirectory() as temp_dir:
        segments_dir = Path(temp_dir)
        
        # Create test segments
        for i in range(3):
            segment = segments_dir / f'{i:04d}.mkv'
            segment.write_bytes(b'x' * 2048)
            
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b'', b'')
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            result = await encoder._concatenate_segments(segments_dir, context.output_path)
            assert result
            mock_exec.assert_called_once()
            cmd = mock_exec.call_args[0]
            assert cmd[0] == 'ffmpeg'
            assert '-f' in cmd
            assert 'concat' in cmd
