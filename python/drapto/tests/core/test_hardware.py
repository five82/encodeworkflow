"""Tests for hardware acceleration support."""

import platform
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from drapto.core.hardware import HardwareAccel, HardwareConfig, HardwareManager


@pytest.fixture
def mock_platform():
    """Mock platform.system."""
    with patch('platform.system') as mock:
        yield mock


@pytest.fixture
def mock_subprocess():
    """Mock subprocess.check_output."""
    with patch('subprocess.check_output') as mock:
        yield mock


@pytest.fixture
def hardware_manager():
    """Create hardware manager for testing."""
    return HardwareManager(ffmpeg_path=Path("/usr/bin/ffmpeg"))


class TestHardwareManager:
    """Tests for HardwareManager."""
    
    def test_detect_acceleration_macos_videotoolbox(self, hardware_manager, mock_platform, mock_subprocess):
        """Test detecting VideoToolbox on macOS."""
        mock_platform.return_value = "Darwin"
        mock_subprocess.return_value = "videotoolbox\nother_accel"
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.VIDEOTOOLBOX
        
        # Should cache detection result
        mock_subprocess.reset_mock()
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.VIDEOTOOLBOX
        mock_subprocess.assert_not_called()
        
    def test_detect_acceleration_macos_no_videotoolbox(self, hardware_manager, mock_platform, mock_subprocess):
        """Test no VideoToolbox on macOS."""
        mock_platform.return_value = "Darwin"
        mock_subprocess.return_value = "other_accel"
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        
    def test_detect_acceleration_linux(self, hardware_manager, mock_platform):
        """Test no hardware acceleration on Linux."""
        mock_platform.return_value = "Linux"
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        
    def test_detect_acceleration_ffmpeg_error(self, hardware_manager, mock_platform, mock_subprocess):
        """Test handling FFmpeg error."""
        mock_platform.return_value = "Darwin"
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, [])
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        
    def test_get_config_videotoolbox(self, hardware_manager):
        """Test getting VideoToolbox configuration."""
        with patch.object(hardware_manager, 'detect_acceleration') as mock_detect:
            mock_detect.return_value = HardwareAccel.VIDEOTOOLBOX
            
            config = hardware_manager.get_config()
            assert config.accel_type == HardwareAccel.VIDEOTOOLBOX
            assert config.ffmpeg_opts == ["-hwaccel", "videotoolbox"]
            assert config.fallback_opts == []
            
    def test_get_config_none(self, hardware_manager):
        """Test getting configuration with no acceleration."""
        with patch.object(hardware_manager, 'detect_acceleration') as mock_detect:
            mock_detect.return_value = HardwareAccel.NONE
            
            config = hardware_manager.get_config()
            assert config.accel_type == HardwareAccel.NONE
            assert config.ffmpeg_opts == []
            assert config.fallback_opts == []
            
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
