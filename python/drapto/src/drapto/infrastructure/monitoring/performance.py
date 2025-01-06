"""Performance tracking utilities."""

import time
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .resources import ResourceMonitor, SystemResources


@dataclass
class PerformanceMetrics:
    """Performance metrics for encoding tasks.
    
    Attributes:
        task_name: Name of the task being tracked
        start_time: Task start time in seconds
        end_time: Task end time in seconds
        duration: Task duration in seconds
        resources: List of resource snapshots during task
        error: Optional error message if task failed
    """
    task_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    resources: List[SystemResources] = None
    error: Optional[str] = None


class PerformanceTracker:
    """Track performance metrics for encoding tasks."""
    
    def __init__(self, resource_monitor: ResourceMonitor):
        """Initialize performance tracker.
        
        Args:
            resource_monitor: Resource monitor instance
        """
        self._logger = logging.getLogger(__name__)
        self._resource_monitor = resource_monitor
        self._active_tasks: Dict[str, PerformanceMetrics] = {}
        self._completed_tasks: List[PerformanceMetrics] = []
        
    def start_task(self, task_name: str) -> None:
        """Start tracking a new task.
        
        Args:
            task_name: Name of the task to track
        """
        if task_name in self._active_tasks:
            self._logger.warning(f"Task {task_name} is already being tracked")
            return
            
        self._active_tasks[task_name] = PerformanceMetrics(
            task_name=task_name,
            start_time=time.time(),
            resources=[]
        )
        
    def end_task(self, task_name: str, error: Optional[str] = None) -> Optional[PerformanceMetrics]:
        """End tracking a task.
        
        Args:
            task_name: Name of the task to end
            error: Optional error message if task failed
            
        Returns:
            Task metrics if task was found, None otherwise
        """
        if task_name not in self._active_tasks:
            self._logger.warning(f"Task {task_name} is not being tracked")
            return None
            
        task = self._active_tasks.pop(task_name)
        task.end_time = time.time()
        task.duration = task.end_time - task.start_time
        task.error = error
        
        self._completed_tasks.append(task)
        return task
        
    def update_task_resources(self, task_name: str) -> None:
        """Update resource metrics for a task.
        
        Args:
            task_name: Name of the task to update
        """
        if task_name not in self._active_tasks:
            self._logger.warning(f"Task {task_name} is not being tracked")
            return
            
        resources = self._resource_monitor.get_resources()
        self._active_tasks[task_name].resources.append(resources)
        
    def get_task_metrics(self, task_name: str) -> Optional[PerformanceMetrics]:
        """Get metrics for a task.
        
        Args:
            task_name: Name of the task
            
        Returns:
            Task metrics if found, None otherwise
        """
        if task_name in self._active_tasks:
            return self._active_tasks[task_name]
            
        for task in self._completed_tasks:
            if task.task_name == task_name:
                return task
                
        return None
        
    def get_all_metrics(self) -> List[PerformanceMetrics]:
        """Get metrics for all tasks.
        
        Returns:
            List of all task metrics
        """
        return list(self._active_tasks.values()) + self._completed_tasks
