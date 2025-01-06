"""Tests for resource monitoring."""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from drapto.infrastructure.monitoring.resources import ResourceMonitor, SystemResources


class TestSystemResources:
    """Test SystemResources implementation."""
    
    def test_system_resources_full(self):
        """Test SystemResources with all fields."""
        resources = SystemResources(
            cpu_percent=50.0,
            memory_percent=60.0,
            disk_percent=20.0,
            disk_free_gb=100.0,
            io_counters={
                'read_bytes': 1000,
                'write_bytes': 2000,
                'read_count': 10,
                'write_count': 20
            },
            network_counters={
                'bytes_sent': 3000,
                'bytes_recv': 4000,
                'packets_sent': 30,
                'packets_recv': 40
            },
            process_count=2
        )
        
        assert resources.cpu_percent == 50.0
        assert resources.memory_percent == 60.0
        assert resources.disk_percent == 20.0
        assert resources.disk_free_gb == 100.0
        assert resources.io_counters is not None
        assert resources.io_counters['read_bytes'] == 1000
        assert resources.network_counters is not None
        assert resources.network_counters['bytes_sent'] == 3000
        assert resources.process_count == 2


class TestResourceMonitor:
    """Test ResourceMonitor implementation."""
    
    @pytest.fixture
    def mock_psutil(self):
        """Mock psutil for testing."""
        with patch('drapto.infrastructure.monitoring.resources.psutil') as mock:
            # Mock CPU usage
            mock.cpu_percent.return_value = 50.0
            
            # Mock memory usage
            memory = Mock()
            memory.percent = 60.0
            mock.virtual_memory.return_value = memory
            
            # Mock disk usage
            disk = Mock()
            disk.free = 100 * 1024 * 1024 * 1024  # 100GB
            disk.total = 500 * 1024 * 1024 * 1024  # 500GB
            disk.percent = 20.0
            mock.disk_usage.return_value = disk
            
            # Mock I/O counters
            io = Mock()
            io.read_bytes = 1000
            io.write_bytes = 2000
            io.read_count = 10
            io.write_count = 20
            mock.disk_io_counters.return_value = io
            
            # Mock network counters
            net = Mock()
            net.bytes_sent = 3000
            net.bytes_recv = 4000
            net.packets_sent = 30
            net.packets_recv = 40
            mock.net_io_counters.return_value = net
            
            # Mock process iteration
            proc1 = Mock()
            proc1.info = {'name': 'ffmpeg'}
            proc2 = Mock()
            proc2.info = {'name': 'ab-av1'}
            mock.process_iter.return_value = [proc1, proc2]
            
            yield mock
    
    @pytest.fixture
    def config(self):
        """Create test config."""
        return {
            'min_disk_gb': 50.0,
            'max_cpu_percent': 80.0,
            'max_memory_percent': 80.0,
            'disk_buffer_factor': 1.5,
            'enable_chunked_encoding': True,
            'segment_length': 15
        }
    
    def test_get_resources_with_io(self, mock_psutil, config):
        """Test getting system resources with I/O stats."""
        monitor = ResourceMonitor(config)
        resources = monitor.get_resources()
        
        assert resources.io_counters is not None
        assert resources.io_counters['read_bytes'] == 1000
        assert resources.io_counters['write_bytes'] == 2000
        assert resources.network_counters is not None
        assert resources.network_counters['bytes_sent'] == 3000
        assert resources.network_counters['bytes_recv'] == 4000
        assert resources.process_count == 2
    
    def test_check_resources_success(self, mock_psutil, config):
        """Test resource check with sufficient resources."""
        monitor = ResourceMonitor(config)
        assert monitor.check_resources() is True
    
    def test_check_resources_low_disk(self, mock_psutil, config):
        """Test resource check with low disk space."""
        # Mock very low disk space
        disk = Mock()
        disk.free = 1 * 1024 * 1024 * 1024  # 1GB
        disk.total = 500 * 1024 * 1024 * 1024  # 500GB
        disk.percent = 99.8
        mock_psutil.disk_usage.return_value = disk
        
        monitor = ResourceMonitor(config)
        assert monitor.check_resources() is False
    
    def test_check_resources_high_cpu(self, mock_psutil, config):
        """Test resource check with high CPU usage."""
        mock_psutil.cpu_percent.return_value = 90.0  # 90% CPU usage
        
        monitor = ResourceMonitor(config)
        assert monitor.check_resources() is False
    
    def test_check_resources_high_memory(self, mock_psutil, config):
        """Test resource check with high memory usage."""
        memory = Mock()
        memory.percent = 90.0  # 90% memory usage
        mock_psutil.virtual_memory.return_value = memory
        
        monitor = ResourceMonitor(config)
        assert monitor.check_resources() is False
    
    def test_check_resources_error(self, mock_psutil, config):
        """Test resource check with error."""
        mock_psutil.cpu_percent.side_effect = Exception("Test error")
        
        monitor = ResourceMonitor(config)
        assert monitor.check_resources() is False
    
    def test_check_resources_with_input_size(self, mock_psutil, config):
        """Test resource check with input size calculation."""
        monitor = ResourceMonitor(config)
        input_size = 10 * 1024 * 1024 * 1024  # 10GB input file
        
        # Should pass with 100GB free
        assert monitor.check_resources(input_size=input_size) is True
        
        # Should fail with only 20GB free
        disk = Mock()
        disk.free = 20 * 1024 * 1024 * 1024  # 20GB
        disk.total = 500 * 1024 * 1024 * 1024  # 500GB
        disk.percent = 96.0
        mock_psutil.disk_usage.return_value = disk
        
        assert monitor.check_resources(input_size=input_size) is False
    
    def test_cleanup_resources(self, tmp_path):
        """Test cleaning up temporary resources."""
        monitor = ResourceMonitor({})
        
        # Create some temporary files
        temp_files = [
            tmp_path / 'temp_video.mkv',
            tmp_path / 'temp_output.mp4',
            tmp_path / 'encode.log',
            tmp_path / 'temp.txt'
        ]
        for file in temp_files:
            file.write_text('test')
            
        # Create an empty directory
        empty_dir = tmp_path / 'empty_dir'
        empty_dir.mkdir()
        
        # Run cleanup
        monitor.cleanup_resources(tmp_path)
        
        # Check files were cleaned up
        for file in temp_files:
            assert not file.exists()
        assert not empty_dir.exists()
    
    def test_optimize_resources(self, mock_psutil):
        """Test resource optimization."""
        with patch('os.system') as mock_system:
            monitor = ResourceMonitor({})
            monitor.optimize_resources()
            
            # Check process priority was set
            if hasattr(os, 'IOPRIO_CLASS_BE'):
                mock_system.assert_called_once()
                assert 'ionice' in mock_system.call_args[0][0]
