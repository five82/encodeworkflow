"""Tests for hardware acceleration detection."""

import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from drapto.infrastructure.hardware.acceleration import (
    HardwareAccel,
    HardwareConfig,
    HardwareManager
)


class TestHardwareManager:
    """Test hardware acceleration detection and configuration."""

    @pytest.fixture
    def mock_ffmpeg_path(self):
        """Mock FFmpeg path validation."""
        with patch.object(HardwareManager, '_is_in_path') as mock:
            mock.return_value = True
            yield mock

    @pytest.fixture
    def hardware_manager(self, mock_ffmpeg_path):
        """Create hardware manager for testing."""
        return HardwareManager(ffmpeg_path=Path("/usr/bin/ffmpeg"))

    def test_ffmpeg_not_found(self):
        """Test handling missing FFmpeg binary."""
        with patch.object(HardwareManager, '_is_in_path') as in_path_mock:
            in_path_mock.return_value = False

            with pytest.raises(FileNotFoundError) as exc:
                HardwareManager(ffmpeg_path=Path("/nonexistent/ffmpeg"))
            assert "FFmpeg not found" in str(exc.value)

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    def test_detect_acceleration_apple_silicon(self, mock_run, mock_machine, mock_system, hardware_manager):
        """Test VideoToolbox detection on macOS."""
        # Mock macOS Apple Silicon
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"
        
        # Mock FFmpeg hwaccels and decoder validation
        def mock_command(*args, **kwargs):
            if "-hwaccels" in args[0]:
                result = MagicMock()
                result.stdout = "videotoolbox\nvdpau\ncuda"
                result.returncode = 0
                return result
            elif "testsrc" in " ".join(args[0]):
                result = MagicMock()
                result.returncode = 0
                return result
            return MagicMock()
        
        mock_run.side_effect = mock_command
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.VIDEOTOOLBOX
        assert hardware_manager.get_ffmpeg_options() == ["-hwaccel", "videotoolbox"]

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_detect_acceleration_linux(self, mock_exists, mock_run, mock_machine, mock_system, hardware_manager):
        """Test VAAPI detection on Linux."""
        # Mock Linux system
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"
        
        # Mock VAAPI device exists
        mock_exists.return_value = True
        
        # Mock FFmpeg, vainfo, and decoder validation
        def mock_command(*args, **kwargs):
            if "-hwaccels" in args[0]:
                result = MagicMock()
                result.stdout = "vaapi\nvdpau\ncuda"
                result.returncode = 0
                return result
            elif "vainfo" in args[0]:
                result = MagicMock()
                result.stdout = "VA-API version: 1.16.0\nDriver version: 22.3.3\nSupported profile and entrypoints:\nVAEntrypointVLD"
                result.returncode = 0
                return result
            elif "testsrc" in " ".join(args[0]):
                result = MagicMock()
                result.returncode = 0
                return result
            return MagicMock()
        
        mock_run.side_effect = mock_command
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.VAAPI
        assert hardware_manager.get_ffmpeg_options() == [
            "-hwaccel", "vaapi",
            "-hwaccel_device", "/dev/dri/renderD128"
        ]

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    def test_detect_acceleration_decoder_failure(self, mock_run, mock_machine, mock_system, hardware_manager):
        """Test handling decoder validation failure."""
        # Mock macOS Apple Silicon
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"
        
        # Mock FFmpeg hwaccels but fail decoder validation
        def mock_command(*args, **kwargs):
            if "-hwaccels" in args[0]:
                result = MagicMock()
                result.stdout = "videotoolbox\nvdpau\ncuda"
                result.returncode = 0
                return result
            elif "testsrc" in " ".join(args[0]):
                raise subprocess.SubprocessError()
            return MagicMock()
        
        mock_run.side_effect = mock_command
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        assert hardware_manager.get_ffmpeg_options() == []

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    def test_detect_acceleration_ffmpeg_error(self, mock_run, mock_machine, mock_system, hardware_manager):
        """Test FFmpeg error handling."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"
        mock_run.side_effect = subprocess.SubprocessError()
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        assert hardware_manager.get_ffmpeg_options() == []

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    def test_detect_acceleration_timeout(self, mock_run, mock_machine, mock_system, hardware_manager):
        """Test FFmpeg timeout handling."""
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"
        mock_run.side_effect = subprocess.TimeoutExpired(["ffmpeg"], 5)
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        assert hardware_manager.get_ffmpeg_options() == []

    def test_disabled_acceleration(self, hardware_manager):
        """Test disabled hardware acceleration."""
        hardware_manager._config = HardwareConfig(enable_hw_accel=False)
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        assert hardware_manager.get_ffmpeg_options() == []

    def test_force_software(self, hardware_manager):
        """Test forced software encoding."""
        hardware_manager._config = HardwareConfig(force_software=True)
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        assert hardware_manager.get_ffmpeg_options() == []

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    def test_unsupported_platform(self, mock_run, mock_machine, mock_system, hardware_manager):
        """Test detection on unsupported platform."""
        # Mock Windows system
        mock_system.return_value = "Windows"
        mock_machine.return_value = "AMD64"
        
        accel = hardware_manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        assert hardware_manager.get_ffmpeg_options() == []
