"""Tests for resource monitoring."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from drapto.monitoring import ResourceMonitor, SystemResources

class TestSystemResources:
    """Test SystemResources implementation."""
    
    def test_disk_calculations(self):
        """Test disk space calculations."""
        resources = SystemResources(
            cpu_percent=50.0,
            memory_percent=60.0,
            disk_percent=20.0,
            disk_free_gb=100.0
        )
        
        assert resources.cpu_percent == 50.0
        assert resources.memory_percent == 60.0
        assert resources.disk_percent == 20.0
        assert resources.disk_free_gb == 100.0

class TestResourceMonitor:
    """Test ResourceMonitor implementation."""
    
    @pytest.fixture
    def mock_psutil(self):
        """Mock psutil for testing."""
        with patch('drapto.monitoring.base.psutil') as mock:
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
    
    def test_get_resources(self, mock_psutil, config):
        """Test getting system resources."""
        monitor = ResourceMonitor(config)
        resources = monitor.get_resources()
        
        assert resources.cpu_percent == 50.0
        assert resources.memory_percent == 60.0
        assert resources.disk_free_gb == 100.0
        assert resources.disk_percent == 20.0
    
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
