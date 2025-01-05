"""Tests for resource monitoring base components."""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch
from pathlib import Path

from drapto.monitoring import ResourceMonitor, SystemResources

class TestSystemResources:
    """Test SystemResources dataclass."""
    
    def test_disk_calculations(self):
        """Test disk space calculations."""
        resources = SystemResources(
            cpu_percent=50.0,
            memory_percent=60.0,
            disk_free_bytes=100 * 1024 * 1024 * 1024,  # 100GB
            disk_total_bytes=500 * 1024 * 1024 * 1024  # 500GB
        )
        
        assert resources.disk_free_gb == 100.0
        assert resources.disk_total_gb == 500.0
        assert resources.disk_percent == 80.0  # (500-100)/500 * 100

class TestResourceMonitor:
    """Test ResourceMonitor implementation."""
    
    @pytest.fixture
    def mock_psutil(self):
        """Create mock psutil module."""
        with patch('drapto.monitoring.base.psutil') as mock:
            # Mock disk usage
            disk_usage = Mock()
            disk_usage.free = 100 * 1024 * 1024 * 1024  # 100GB
            disk_usage.total = 500 * 1024 * 1024 * 1024  # 500GB
            mock.disk_usage.return_value = disk_usage
            
            # Mock CPU usage
            mock.cpu_percent.return_value = 50.0
            
            # Mock memory usage
            memory = Mock()
            memory.percent = 60.0
            mock.virtual_memory.return_value = memory
            
            yield mock
    
    def test_get_resources(self, mock_psutil):
        """Test getting system resources."""
        monitor = ResourceMonitor()
        resources = monitor.get_resources()
        
        assert resources.cpu_percent == 50.0
        assert resources.memory_percent == 60.0
        assert resources.disk_free_gb == 100.0
        assert resources.disk_total_gb == 500.0
    
    def test_check_resources_success(self, mock_psutil):
        """Test resource check with sufficient resources."""
        monitor = ResourceMonitor(
            min_disk_gb=50.0,
            max_cpu_percent=80.0,
            max_memory_percent=80.0
        )
        assert monitor.check_resources() is True
    
    def test_check_resources_low_disk(self, mock_psutil):
        """Test resource check with low disk space."""
        monitor = ResourceMonitor(min_disk_gb=200.0)  # Require 200GB
        assert monitor.check_resources() is False
    
    def test_check_resources_high_cpu(self, mock_psutil):
        """Test resource check with high CPU usage."""
        monitor = ResourceMonitor(max_cpu_percent=40.0)  # Max 40%
        assert monitor.check_resources() is False
    
    def test_check_resources_high_memory(self, mock_psutil):
        """Test resource check with high memory usage."""
        monitor = ResourceMonitor(max_memory_percent=50.0)  # Max 50%
        assert monitor.check_resources() is False
    
    def test_check_resources_error(self, mock_psutil):
        """Test resource check with error."""
        mock_psutil.disk_usage.side_effect = Exception("Test error")
        monitor = ResourceMonitor()
        assert monitor.check_resources() is False
