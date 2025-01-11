"""Tests for hardware acceleration support."""

import platform
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from drapto.infrastructure.hardware.acceleration import (
    HardwareAccel,
    HardwareConfig,
    HardwareManager
)


@pytest.fixture
def mock_platform():
    """Mock platform module."""
    with patch('platform.system') as sys_mock, \
         patch('platform.machine') as machine_mock, \
         patch('platform.processor') as proc_mock, \
         patch('platform.release') as rel_mock:
        yield {
            'system': sys_mock,
            'machine': machine_mock,
            'processor': proc_mock,
            'release': rel_mock
        }


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.check_output."""
    with patch('subprocess.check_output') as mock:
        yield mock


@pytest.fixture
def mock_path():
    """Mock Path.is_file."""
    with patch('pathlib.Path.is_file') as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def hardware_manager(mock_path):
    """Create hardware manager for testing."""
    return HardwareManager(ffmpeg_path=Path("/usr/bin/ffmpeg"))


class TestHardwareManager:
    """Tests for HardwareManager."""
    
    def test_detect_acceleration_apple_silicon(self, hardware_manager, mock_platform, mock_subprocess):
        """Test detecting VideoToolbox on Apple Silicon."""
        # Setup platform as Apple Silicon
        mock_platform['system'].return_value = "Darwin"
        mock_platform['machine'].return_value = "arm64"
        mock_platform['processor'].return_value = "arm"
        mock_platform['release'].return_value = "20.0.0"
        mock_subprocess.return_value = "videotoolbox\nother_accel"
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.VIDEOTOOLBOX
        
        # Should cache detection result
        mock_subprocess.reset_mock()
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.VIDEOTOOLBOX
        mock_subprocess.assert_not_called()
        
    def test_detect_acceleration_linux(self, hardware_manager, mock_platform, mock_subprocess):
        """Test no hardware acceleration on Linux."""
        mock_platform['system'].return_value = "Linux"
        mock_platform['machine'].return_value = "x86_64"
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        mock_subprocess.assert_not_called()  # Should not check FFmpeg on Linux
        
    def test_detect_acceleration_ffmpeg_error(self, hardware_manager, mock_platform, mock_subprocess):
        """Test handling FFmpeg error."""
        # Setup platform as Apple Silicon
        mock_platform['system'].return_value = "Darwin"
        mock_platform['machine'].return_value = "arm64"
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, [], stderr=b"error")
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        
    def test_detect_acceleration_timeout(self, hardware_manager, mock_platform, mock_subprocess):
        """Test handling FFmpeg timeout."""
        # Setup platform as Apple Silicon
        mock_platform['system'].return_value = "Darwin"
        mock_platform['machine'].return_value = "arm64"
        mock_subprocess.side_effect = subprocess.TimeoutExpired([], 5)
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        
    def test_get_config_videotoolbox(self, hardware_manager, mock_platform):
        """Test getting VideoToolbox configuration."""
        # Setup platform as Apple Silicon
        mock_platform['system'].return_value = "Darwin"
        mock_platform['machine'].return_value = "arm64"
        
        with patch.object(hardware_manager, 'detect_acceleration') as mock_detect:
            mock_detect.return_value = HardwareAccel.VIDEOTOOLBOX
            
            config = hardware_manager.get_config()
            assert config.accel_type == HardwareAccel.VIDEOTOOLBOX
            assert config.ffmpeg_opts == ["-hwaccel", "videotoolbox"]
            assert config.fallback_opts == []
            assert config.platform_info == hardware_manager._get_platform_info()
            
    def test_get_config_none(self, hardware_manager, mock_platform):
        """Test getting configuration with no acceleration."""
        # Setup platform as Linux
        mock_platform['system'].return_value = "Linux"
        mock_platform['machine'].return_value = "x86_64"
        
        with patch.object(hardware_manager, 'detect_acceleration') as mock_detect:
            mock_detect.return_value = HardwareAccel.NONE
            
            config = hardware_manager.get_config()
            assert config.accel_type == HardwareAccel.NONE
            assert config.ffmpeg_opts == []
            assert config.fallback_opts == []
            assert config.platform_info == hardware_manager._get_platform_info()
            
    def test_monitor_performance(self, hardware_manager):
        """Test monitoring performance."""
        encoder = Mock()
        encoder.get_resources.return_value = {
            'cpu_percent': 50.0,
            'memory_percent': 25.0
        }
        
        with patch.object(hardware_manager, '_detected_accel', HardwareAccel.VIDEOTOOLBOX):
            metrics = hardware_manager.monitor_performance(encoder)
            assert metrics['cpu_percent'] == 50.0
            assert metrics['memory_percent'] == 25.0
            assert metrics['hw_accel_type'] == 'VIDEOTOOLBOX'
            # Should include platform info when using hardware acceleration
            assert all(k.startswith('platform_') for k in metrics.keys() 
                      if k not in ['cpu_percent', 'memory_percent', 'hw_accel_type'])
            
    def test_monitor_performance_no_accel(self, hardware_manager):
        """Test monitoring performance without acceleration."""
        encoder = Mock()
        encoder.get_resources.return_value = {
            'cpu_percent': 50.0,
            'memory_percent': 25.0
        }
        
        with patch.object(hardware_manager, '_detected_accel', HardwareAccel.NONE):
            metrics = hardware_manager.monitor_performance(encoder)
            assert metrics['cpu_percent'] == 50.0
            assert metrics['memory_percent'] == 25.0
            assert metrics['hw_accel_type'] == 'NONE'
            # Should not include platform info when not using hardware acceleration
            assert all(not k.startswith('platform_') for k in metrics.keys())
            
    def test_ffmpeg_not_found(self):
        """Test handling missing FFmpeg binary."""
        with patch('pathlib.Path.is_file') as is_file_mock, \
             patch.object(HardwareManager, '_is_in_path') as in_path_mock:
            is_file_mock.return_value = False
            in_path_mock.return_value = False
            
            with pytest.raises(FileNotFoundError) as exc:
                HardwareManager(ffmpeg_path=Path("/nonexistent/ffmpeg"))
            assert "FFmpeg binary not found" in str(exc.value)
