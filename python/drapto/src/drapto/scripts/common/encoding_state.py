#!/usr/bin/env python3

"""
Encoding State Management

This module handles state tracking for video encoding jobs, including:
- Job status and progress
- Input/output file information
- Encoding statistics
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

class JobStatus(Enum):
    """Status of an encoding job"""
    PENDING = "pending"
    INITIALIZING = "initializing"
    PREPARING = "preparing"
    ENCODING = "encoding"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class EncodingStats:
    """Statistics for an encoding job"""
    input_size: int = 0
    output_size: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    vmaf_score: float = 0.0

@dataclass
class EncodingJob:
    """Represents a single encoding job"""
    job_id: str
    input_file: str
    output_file: str
    status: JobStatus
    strategy: str
    stats: EncodingStats
    error_message: Optional[str] = None

class EncodingState:
    """Manages state for all encoding jobs"""
    
    def __init__(self, state_dir: str):
        """Initialize encoding state manager
        
        Args:
            state_dir: Directory to store state files
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, EncodingJob] = {}
        self._load_state()
    
    def create_job(self, input_file: str, output_file: str, strategy: str) -> str:
        """Create a new encoding job
        
        Args:
            input_file: Path to input video file
            output_file: Path to output video file
            strategy: Name of encoding strategy to use
            
        Returns:
            job_id: Unique identifier for the job
        """
        job_id = str(int(time.time()))
        job = EncodingJob(
            job_id=job_id,
            input_file=input_file,
            output_file=output_file,
            status=JobStatus.PENDING,
            strategy=strategy,
            stats=EncodingStats(start_time=time.time())
        )
        self.jobs[job_id] = job
        self._save_state()
        return job_id
    
    def update_job_status(self, job_id: str, status: JobStatus, error: str = None) -> None:
        """Update status of an encoding job
        
        Args:
            job_id: Job identifier
            status: New job status
            error: Optional error message if job failed
        """
        if job_id not in self.jobs:
            raise KeyError(f"Job {job_id} not found")
        
        job = self.jobs[job_id]
        job.status = status
        if error:
            job.error_message = error
        if status == JobStatus.COMPLETED:
            job.stats.end_time = time.time()
        self._save_state()
    
    def update_job_stats(self, job_id: str, **kwargs) -> None:
        """Update statistics for an encoding job
        
        Args:
            job_id: Job identifier
            **kwargs: Statistics to update (input_size, output_size, vmaf_score)
        """
        if job_id not in self.jobs:
            raise KeyError(f"Job {job_id} not found")
        
        job = self.jobs[job_id]
        for key, value in kwargs.items():
            if hasattr(job.stats, key):
                setattr(job.stats, key, value)
        self._save_state()
    
    def get_job(self, job_id: str) -> EncodingJob:
        """Get information about an encoding job
        
        Args:
            job_id: Job identifier
            
        Returns:
            EncodingJob: Job information
        """
        if job_id not in self.jobs:
            raise KeyError(f"Job {job_id} not found")
        return self.jobs[job_id]
    
    def get_all_jobs(self) -> List[EncodingJob]:
        """Get information about all encoding jobs
        
        Returns:
            List[EncodingJob]: List of all jobs
        """
        return list(self.jobs.values())
    
    def _save_state(self) -> None:
        """Save current state to disk"""
        state_file = self.state_dir / "encoding_state.json"
        state = {
            job_id: asdict(job)
            for job_id, job in self.jobs.items()
        }
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _load_state(self) -> None:
        """Load state from disk"""
        state_file = self.state_dir / "encoding_state.json"
        if not state_file.exists():
            return
        
        with open(state_file) as f:
            state = json.load(f)
        
        for job_id, job_dict in state.items():
            job_dict['status'] = JobStatus(job_dict['status'])
            job_dict['stats'] = EncodingStats(**job_dict['stats'])
            self.jobs[job_id] = EncodingJob(**job_dict)
