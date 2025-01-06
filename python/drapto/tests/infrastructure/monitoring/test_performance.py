"""Tests for performance tracking."""

import time
import pytest
from unittest.mock import Mock, patch

from drapto.infrastructure.monitoring.resources import ResourceMonitor, SystemResources
from drapto.infrastructure.monitoring.performance import PerformanceTracker, PerformanceMetrics


@pytest.fixture
def mock_time():
    """Mock time for testing."""
    with patch('drapto.infrastructure.monitoring.performance.time') as mock:
        mock.time.side_effect = [1.0, 2.0, 3.0, 4.0]  # Sequential times
        yield mock


@pytest.fixture
def mock_resources():
    """Create mock system resources."""
    return SystemResources(
        cpu_percent=50.0,
        memory_percent=60.0,
        disk_percent=20.0,
        disk_free_gb=100.0,
        io_counters={'read_bytes': 1000},
        network_counters={'bytes_sent': 2000},
        process_count=1
    )


@pytest.fixture
def mock_monitor(mock_resources):
    """Create mock resource monitor."""
    monitor = Mock(spec=ResourceMonitor)
    monitor.get_resources.return_value = mock_resources
    return monitor


class TestPerformanceMetrics:
    """Test PerformanceMetrics implementation."""
    
    def test_performance_metrics(self):
        """Test PerformanceMetrics fields."""
        metrics = PerformanceMetrics(
            task_name="test_task",
            start_time=1.0,
            end_time=2.0,
            duration=1.0,
            resources=[],
            error=None
        )
        
        assert metrics.task_name == "test_task"
        assert metrics.start_time == 1.0
        assert metrics.end_time == 2.0
        assert metrics.duration == 1.0
        assert metrics.resources == []
        assert metrics.error is None


class TestPerformanceTracker:
    """Test PerformanceTracker implementation."""
    
    def test_start_task(self, mock_time, mock_monitor):
        """Test starting task tracking."""
        tracker = PerformanceTracker(mock_monitor)
        tracker.start_task("test_task")
        
        metrics = tracker.get_task_metrics("test_task")
        assert metrics is not None
        assert metrics.task_name == "test_task"
        assert metrics.start_time == 1.0
        assert metrics.end_time is None
        assert metrics.duration is None
        assert metrics.resources == []
        
    def test_end_task(self, mock_time, mock_monitor):
        """Test ending task tracking."""
        tracker = PerformanceTracker(mock_monitor)
        tracker.start_task("test_task")
        metrics = tracker.end_task("test_task")
        
        assert metrics is not None
        assert metrics.end_time == 2.0
        assert metrics.duration == 1.0
        assert metrics.error is None
        
    def test_end_task_with_error(self, mock_time, mock_monitor):
        """Test ending task with error."""
        tracker = PerformanceTracker(mock_monitor)
        tracker.start_task("test_task")
        metrics = tracker.end_task("test_task", error="Test error")
        
        assert metrics is not None
        assert metrics.error == "Test error"
        
    def test_update_task_resources(self, mock_time, mock_monitor, mock_resources):
        """Test updating task resources."""
        tracker = PerformanceTracker(mock_monitor)
        tracker.start_task("test_task")
        tracker.update_task_resources("test_task")
        
        metrics = tracker.get_task_metrics("test_task")
        assert metrics is not None
        assert len(metrics.resources) == 1
        assert metrics.resources[0] == mock_resources
        
    def test_get_task_metrics_active(self, mock_time, mock_monitor):
        """Test getting metrics for active task."""
        tracker = PerformanceTracker(mock_monitor)
        tracker.start_task("test_task")
        
        metrics = tracker.get_task_metrics("test_task")
        assert metrics is not None
        assert metrics.task_name == "test_task"
        
    def test_get_task_metrics_completed(self, mock_time, mock_monitor):
        """Test getting metrics for completed task."""
        tracker = PerformanceTracker(mock_monitor)
        tracker.start_task("test_task")
        tracker.end_task("test_task")
        
        metrics = tracker.get_task_metrics("test_task")
        assert metrics is not None
        assert metrics.task_name == "test_task"
        assert metrics.end_time is not None
        
    def test_get_all_metrics(self, mock_time, mock_monitor):
        """Test getting all task metrics."""
        tracker = PerformanceTracker(mock_monitor)
        tracker.start_task("active_task")
        tracker.start_task("completed_task")
        tracker.end_task("completed_task")
        
        metrics = tracker.get_all_metrics()
        assert len(metrics) == 2
        assert any(m.task_name == "active_task" for m in metrics)
        assert any(m.task_name == "completed_task" for m in metrics)
