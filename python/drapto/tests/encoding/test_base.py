"""Tests for base encoding components."""

import os
import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from drapto.encoding import BaseEncoder, EncodingContext

class TestEncodingContext:
    """Test EncodingContext implementation."""
    
    def test_context_creation(self):
        """Test creating encoding context."""
        context = EncodingContext(
            input_path=Path("/input.mkv"),
            output_path=Path("/output.mkv"),
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        assert context.input_path == Path("/input.mkv")
        assert context.output_path == Path("/output.mkv")
        assert context.target_vmaf == 93.0
        assert context.preset == 6
        assert context.svt_params == "film-grain=0:film-grain-denoise=0"
        assert context.crop_filter is None

class TestBaseEncoder:
    """Test BaseEncoder implementation."""
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        return {
            'min_disk_gb': 50.0,
            'max_cpu_percent': 80.0,
            'max_memory_percent': 80.0,
            'disk_buffer_factor': 1.5,
            'enable_chunked_encoding': True,
            'segment_length': 15,
            'ffmpeg': 'ffmpeg',
            'ffprobe': 'ffprobe'
        }
    
    @pytest.fixture
    def encoder(self, config):
        """Create test encoder."""
        return BaseEncoder(config)
    
    @pytest.fixture
    def input_path(self, tmp_path):
        """Create test input file."""
        path = tmp_path / "input.mkv"
        path.touch()
        with open(path, "wb") as f:
            f.write(b"dummy content")
        return path
    
    @pytest.fixture
    def output_path(self, tmp_path):
        """Create test output path."""
        return tmp_path / "output.mkv"
    
    @pytest.fixture
    def mock_which(self):
        """Mock shutil.which to make dependencies available."""
        with patch('shutil.which') as mock:
            mock.return_value = True
            yield mock
    
    @pytest.fixture
    def mock_run_command(self):
        """Mock _run_command to return test data."""
        with patch.object(BaseEncoder, '_run_command', new_callable=AsyncMock) as mock:
            mock.return_value = None
            yield mock
    
    @pytest.mark.asyncio
    async def test_validate_input_file_exists(self, encoder, input_path, output_path, mock_which):
        """Test input validation with existing file."""
        context = EncodingContext(
            input_path=input_path,
            output_path=output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await encoder._validate_input(context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_input_file_missing(self, encoder, tmp_path, mock_which):
        """Test input validation with missing file."""
        context = EncodingContext(
            input_path=tmp_path / "nonexistent.mkv",
            output_path=tmp_path / "output.mkv",
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await encoder._validate_input(context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_output_success(self, encoder, input_path, output_path, mock_which, mock_run_command):
        """Test output validation with valid file."""
        # Create dummy output file
        output_path.touch()
        with open(output_path, "wb") as f:
            f.write(b"dummy content")
            
        # Mock ffprobe responses
        mock_run_command.side_effect = [
            'av1',  # video codec
            'opus\nopus',  # audio codecs
            '60.0',  # input duration
            '60.0'   # output duration
        ]
            
        context = EncodingContext(
            input_path=input_path,
            output_path=output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await encoder._validate_output(context)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_output_empty_file(self, encoder, input_path, output_path, mock_which):
        """Test output validation with empty file."""
        # Create empty output file
        output_path.touch()
            
        context = EncodingContext(
            input_path=input_path,
            output_path=output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await encoder._validate_output(context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_input_low_resources(self, encoder, input_path, output_path, mock_which):
        """Test input validation with low resources."""
        with patch('drapto.monitoring.base.psutil') as mock_psutil:
            # Mock very low disk space
            disk_usage = Mock()
            disk_usage.free = 1 * 1024 * 1024 * 1024  # 1GB
            disk_usage.total = 500 * 1024 * 1024 * 1024  # 500GB
            mock_psutil.disk_usage.return_value = disk_usage
            
            context = EncodingContext(
                input_path=input_path,
                output_path=output_path,
                target_vmaf=93.0,
                preset=6,
                svt_params="film-grain=0:film-grain-denoise=0"
            )
            
            result = await encoder._validate_input(context)
            assert result is False
    
    def test_get_resources(self, encoder, tmp_path):
        """Test getting resource usage."""
        resources = encoder.get_resources(tmp_path)
        
        assert 'cpu_percent' in resources
        assert 'memory_percent' in resources
        assert 'disk_percent' in resources
        assert 'disk_free_gb' in resources
    
    def test_check_dependencies_success(self, encoder, mock_which):
        """Test dependency check with all dependencies available."""
        assert encoder._check_dependencies() is True
        assert mock_which.call_count >= 4  # ffmpeg, ffprobe, mediainfo, bc
    
    def test_check_dependencies_missing_ffmpeg(self, encoder, mock_which):
        """Test dependency check with missing ffmpeg."""
        def mock_which_except_ffmpeg(cmd):
            return cmd != 'ffmpeg'
        mock_which.side_effect = mock_which_except_ffmpeg
        
        assert encoder._check_dependencies() is False
    
    def test_check_dependencies_missing_mediainfo(self, encoder, mock_which):
        """Test dependency check with missing mediainfo."""
        def mock_which_except_mediainfo(cmd):
            return cmd != 'mediainfo'
        mock_which.side_effect = mock_which_except_mediainfo
        
        assert encoder._check_dependencies() is False
    
    def test_check_dependencies_missing_bc(self, encoder, mock_which):
        """Test dependency check with missing bc."""
        def mock_which_except_bc(cmd):
            return cmd != 'bc'
        mock_which.side_effect = mock_which_except_bc
        
        assert encoder._check_dependencies() is False
    
    def test_check_dependencies_missing_abav1(self, encoder, mock_which):
        """Test dependency check with missing ab-av1."""
        def mock_which_except_abav1(cmd):
            return cmd != 'ab-av1'
        mock_which.side_effect = mock_which_except_abav1
        
        # Should still pass since chunked encoding is not required
        encoder.config['enable_chunked_encoding'] = False
        assert encoder._check_dependencies() is True
        
        # Should fail when chunked encoding is enabled
        encoder.config['enable_chunked_encoding'] = True
        assert encoder._check_dependencies() is False
    
    @pytest.mark.asyncio
    async def test_validate_output_wrong_video_codec(self, encoder, input_path, output_path, mock_which, mock_run_command):
        """Test output validation with wrong video codec."""
        output_path.touch()
        with open(output_path, "wb") as f:
            f.write(b"dummy content")
            
        # Mock ffprobe responses
        mock_run_command.side_effect = [
            'h264',  # wrong video codec
            'opus\nopus',
            '60.0',
            '60.0'
        ]
            
        context = EncodingContext(
            input_path=input_path,
            output_path=output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await encoder._validate_output(context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_output_wrong_audio_codec(self, encoder, input_path, output_path, mock_which, mock_run_command):
        """Test output validation with wrong audio codec."""
        output_path.touch()
        with open(output_path, "wb") as f:
            f.write(b"dummy content")
            
        # Mock ffprobe responses
        mock_run_command.side_effect = [
            'av1',
            'aac\naac',  # wrong audio codec
            '60.0',
            '60.0'
        ]
            
        context = EncodingContext(
            input_path=input_path,
            output_path=output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await encoder._validate_output(context)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_output_duration_mismatch(self, encoder, input_path, output_path, mock_which, mock_run_command):
        """Test output validation with mismatched durations."""
        output_path.touch()
        with open(output_path, "wb") as f:
            f.write(b"dummy content")
            
        # Mock ffprobe responses
        mock_run_command.side_effect = [
            'av1',
            'opus\nopus',
            '60.0',  # input duration
            '65.0'   # output duration (too different)
        ]
            
        context = EncodingContext(
            input_path=input_path,
            output_path=output_path,
            target_vmaf=93.0,
            preset=6,
            svt_params="film-grain=0:film-grain-denoise=0"
        )
        
        result = await encoder._validate_output(context)
        assert result is False
