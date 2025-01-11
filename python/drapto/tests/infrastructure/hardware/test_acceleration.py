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


class TestHardwareAcceleration:
    """Test hardware acceleration detection and configuration."""

    def test_init_missing_ffmpeg(self):
        """Test initialization with missing ffmpeg."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError):
                HardwareManager(ffmpeg_path=Path("nonexistent"))

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    def test_videotoolbox_detection(self, mock_run, mock_machine, mock_system):
        """Test VideoToolbox detection on macOS."""
        # Mock macOS Apple Silicon
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "arm64"
        
        # Mock FFmpeg hwaccels output
        mock_run.return_value.stdout = "Hardware acceleration methods: videotoolbox"
        mock_run.return_value.returncode = 0
        
        manager = HardwareManager()
        accel = manager.detect_acceleration()
        
        assert accel == HardwareAccel.VIDEOTOOLBOX
        assert manager.get_ffmpeg_options() == ["-hwaccel", "videotoolbox"]

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_vaapi_detection(self, mock_exists, mock_run, mock_machine, mock_system):
        """Test VAAPI detection on Linux."""
        # Mock Linux system
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"
        
        # Mock VAAPI device exists
        mock_exists.return_value = True
        
        # Mock FFmpeg and vainfo output
        def mock_command(*args, **kwargs):
            if "-version" in args[0]:
                result = MagicMock()
                result.returncode = 0
                return result
            elif "-hwaccels" in args[0]:
                # FFmpeg hwaccels output
                result = MagicMock()
                result.stdout = "vaapi\nvdpau\ncuda"
                result.returncode = 0
                return result
            elif "vainfo" in args[0]:
                # vainfo output
                result = MagicMock()
                result.stdout = "VA-API version: 1.16.0\nDriver version: 22.3.3\nSupported profile and entrypoints:\nVAEntrypointVLD"
                result.returncode = 0
                return result
            return MagicMock()
        
        mock_run.side_effect = mock_command
        
        manager = HardwareManager()
        accel = manager.detect_acceleration()
        
        assert accel == HardwareAccel.VAAPI
        assert manager.get_ffmpeg_options() == [
            "-hwaccel", "vaapi",
            "-hwaccel_device", "/dev/dri/renderD128"
        ]

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    def test_vaapi_missing_device(self, mock_run, mock_machine, mock_system):
        """Test VAAPI detection with missing device."""
        # Mock Linux system
        mock_system.return_value = "Linux"
        mock_machine.return_value = "x86_64"
        
        # Mock device does not exist
        with patch("pathlib.Path.exists", return_value=False):
            manager = HardwareManager()
            accel = manager.detect_acceleration()
            
            assert accel == HardwareAccel.NONE
            assert manager.get_ffmpeg_options() == []

    def test_disabled_acceleration(self):
        """Test disabled hardware acceleration."""
        manager = HardwareManager()
        manager._config = HardwareConfig(enable_hw_accel=False)
        
        accel = manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        assert manager.get_ffmpeg_options() == []

    def test_force_software(self):
        """Test forced software encoding."""
        manager = HardwareManager()
        manager._config = HardwareConfig(force_software=True)
        
        accel = manager.detect_acceleration()
        assert accel == HardwareAccel.NONE
        assert manager.get_ffmpeg_options() == []

    @patch("platform.system")
    @patch("platform.machine")
    @patch("subprocess.run")
    def test_unsupported_platform(self, mock_run, mock_machine, mock_system):
        """Test detection on unsupported platform."""
        # Mock Windows system
        mock_system.return_value = "Windows"
        mock_machine.return_value = "AMD64"
        
        manager = HardwareManager()
        accel = manager.detect_acceleration()
        
        assert accel == HardwareAccel.NONE
        assert manager.get_ffmpeg_options() == []
