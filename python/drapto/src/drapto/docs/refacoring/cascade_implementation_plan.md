# Drapto Cascade-Specific Implementation Plan

## Overview
This document outlines the step-by-step refactoring process using Cascade's specific tools and capabilities. Each step includes exact commands and validations.

## Phase 0: Analysis and Preparation

### 0.1 Codebase Analysis
```python
# Find all Python files in project
find_by_name(
    SearchDirectory="/home/ken/projects/encodeworkflow/python/drapto/src/drapto",
    Pattern="**/*.py"
)

# Locate main entry points
grep_search(
    SearchDirectory="/home/ken/projects/encodeworkflow/python/drapto/src/drapto",
    Query="if __name__ == '__main__'",
    MatchPerLine=true,
    Includes=["*.py"],
    CaseInsensitive=false
)

# Find core classes
grep_search(
    SearchDirectory="/home/ken/projects/encodeworkflow/python/drapto/src/drapto",
    Query="class.*Processor|class.*Handler|class.*Manager",
    MatchPerLine=true,
    Includes=["*.py"],
    CaseInsensitive=false
)
```

### 0.2 Create New Structure
```python
# Create core module
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/core/__init__.py",
    CodeContent="\"\"\"Core domain models and interfaces\"\"\"",
    EmptyFile=false
)

# Create services module
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/services/__init__.py",
    CodeContent="\"\"\"Service implementations\"\"\"",
    EmptyFile=false
)

# Create infrastructure module
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/infrastructure/__init__.py",
    CodeContent="\"\"\"Infrastructure components\"\"\"",
    EmptyFile=false
)
```

## Phase 1: Core Domain Models

### 1.1 Create Base Models
```python
# Create models.py
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/core/models.py",
    CodeContent="""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any

@dataclass
class VideoMetadata:
    path: Path
    is_dolby_vision: bool
    resolution: tuple[int, int]
    frame_rate: float
    duration: float

@dataclass
class ProcessingState:
    stage: str
    metadata: VideoMetadata
    resources: Dict[str, Any]
    errors: List[str]
""",
    EmptyFile=false
)
```

### 1.2 Create Interfaces
```python
# Create interfaces.py
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/core/interfaces.py",
    CodeContent="""
from typing import Protocol, List, Optional
from pathlib import Path
from .models import VideoMetadata, ProcessingState

class IDetectionService(Protocol):
    async def analyze_video(self, input_path: Path) -> VideoMetadata: ...
    async def detect_dolby_vision(self, input_path: Path) -> bool: ...

class ISegmentationService(Protocol):
    async def segment_video(self, input_path: Path, work_dir: Path) -> List[Path]: ...
    async def validate_segments(self, segments: List[Path]) -> bool: ...

class IEncodingService(Protocol):
    async def encode_video(self, input_path: Path, output_path: Path) -> bool: ...
    async def validate_output(self, output_path: Path) -> bool: ...
""",
    EmptyFile=false
)
```

## Phase 2: Infrastructure Layer

### 2.1 FFmpeg Wrapper
```python
# Create ffmpeg wrapper
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/infrastructure/ffmpeg.py",
    CodeContent="""
import asyncio
import logging
from pathlib import Path
from typing import List, Optional

class FFmpegError(Exception):
    pass

class FFmpegWrapper:
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    async def run_command(self, args: List[str]) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                'ffmpeg',
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise FFmpegError(f"FFmpeg failed: {stderr.decode()}")
            return stdout.decode()
        except Exception as e:
            self._logger.error(f"FFmpeg error: {e}")
            raise
""",
    EmptyFile=false
)
```

### 2.2 Resource Manager
```python
# Create resource manager
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/infrastructure/resources.py",
    CodeContent="""
import logging
from pathlib import Path
from typing import Set, Dict, Any

class Resource:
    def __init__(self, name: str, path: Optional[Path] = None):
        self.name = name
        self.path = path
        self.is_active = False

class ResourceManager:
    def __init__(self):
        self._resources: Dict[str, Resource] = {}
        self._logger = logging.getLogger(__name__)

    async def acquire(self, name: str, path: Optional[Path] = None) -> Resource:
        resource = Resource(name, path)
        resource.is_active = True
        self._resources[name] = resource
        self._logger.info(f"Acquired resource: {name}")
        return resource

    async def release(self, name: str) -> None:
        if resource := self._resources.get(name):
            resource.is_active = False
            self._logger.info(f"Released resource: {name}")
""",
    EmptyFile=false
)
```

## Phase 3: Detection Service

### 3.1 Create Service
```python
# Create detection service
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/services/detection.py",
    CodeContent="""
import logging
from pathlib import Path
from typing import Optional
from ..core.models import VideoMetadata
from ..core.interfaces import IDetectionService
from ..infrastructure.ffmpeg import FFmpegWrapper

class DetectionService(IDetectionService):
    def __init__(self, ffmpeg: FFmpegWrapper):
        self._ffmpeg = ffmpeg
        self._logger = logging.getLogger(__name__)

    async def analyze_video(self, input_path: Path) -> VideoMetadata:
        # Implementation
        pass

    async def detect_dolby_vision(self, input_path: Path) -> bool:
        # Implementation
        pass
""",
    EmptyFile=false
)
```

### 3.2 Move Legacy Code
```python
# First find legacy detection code
grep_search(
    SearchDirectory="/home/ken/projects/encodeworkflow/python/drapto/src/drapto",
    Query="def detect|def analyze",
    MatchPerLine=true,
    Includes=["*.py"],
    CaseInsensitive=false
)

# Move to legacy module
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/services/legacy/detection.py",
    CodeContent="# Legacy detection code moved here",
    EmptyFile=false
)
```

## Phase 4: Segmentation Service

### 4.1 Create Service
```python
# Create segmentation service
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/services/segmentation.py",
    CodeContent="""
import logging
from pathlib import Path
from typing import List
from ..core.interfaces import ISegmentationService
from ..infrastructure.ffmpeg import FFmpegWrapper
from ..infrastructure.resources import ResourceManager

class SegmentationService(ISegmentationService):
    def __init__(self, 
                 ffmpeg: FFmpegWrapper,
                 resource_manager: ResourceManager):
        self._ffmpeg = ffmpeg
        self._resources = resource_manager
        self._logger = logging.getLogger(__name__)

    async def segment_video(self, 
                          input_path: Path,
                          work_dir: Path) -> List[Path]:
        # Implementation
        pass

    async def validate_segments(self, segments: List[Path]) -> bool:
        # Implementation
        pass
""",
    EmptyFile=false
)
```

## Phase 5: Encoding Service

### 5.1 Create Base Service
```python
# Create encoding base
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/services/encoding/base.py",
    CodeContent="""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from ...core.interfaces import IEncodingService
from ...infrastructure.ffmpeg import FFmpegWrapper

class BaseEncoder(IEncodingService, ABC):
    def __init__(self, ffmpeg: FFmpegWrapper):
        self._ffmpeg = ffmpeg

    @abstractmethod
    async def encode_video(self, 
                          input_path: Path,
                          output_path: Path) -> bool:
        pass

    @abstractmethod
    async def validate_output(self, output_path: Path) -> bool:
        pass
""",
    EmptyFile=false
)
```

### 5.2 Create Specific Encoders
```python
# Create DV encoder
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/services/encoding/dolby_vision.py",
    CodeContent="""
from pathlib import Path
from .base import BaseEncoder

class DolbyVisionEncoder(BaseEncoder):
    async def encode_video(self,
                          input_path: Path,
                          output_path: Path) -> bool:
        # Implementation
        pass

    async def validate_output(self, output_path: Path) -> bool:
        # Implementation
        pass
""",
    EmptyFile=false
)

# Create SVT encoder
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/services/encoding/svt.py",
    CodeContent="""
from pathlib import Path
from .base import BaseEncoder

class SVTEncoder(BaseEncoder):
    async def encode_video(self,
                          input_path: Path,
                          output_path: Path) -> bool:
        # Implementation
        pass

    async def validate_output(self, output_path: Path) -> bool:
        # Implementation
        pass
""",
    EmptyFile=false
)
```

## Phase 6: Orchestration

### 6.1 Create Orchestrator
```python
# Create orchestrator
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/services/orchestrator.py",
    CodeContent="""
import logging
from pathlib import Path
from typing import Optional
from ..core.interfaces import (
    IDetectionService,
    ISegmentationService,
    IEncodingService
)
from ..core.models import ProcessingState
from ..infrastructure.resources import ResourceManager

class VideoOrchestrator:
    def __init__(self,
                 detection: IDetectionService,
                 segmentation: ISegmentationService,
                 encoding: IEncodingService,
                 resources: ResourceManager):
        self._detection = detection
        self._segmentation = segmentation
        self._encoding = encoding
        self._resources = resources
        self._logger = logging.getLogger(__name__)

    async def process_video(self,
                          input_path: Path,
                          output_path: Path) -> bool:
        try:
            # Implementation
            pass
        except Exception as e:
            self._logger.error(f"Processing failed: {e}")
            return False
""",
    EmptyFile=false
)
```

## Phase 7: CLI Updates

### 7.1 Update CLI
```python
# Update CLI
edit_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/src/drapto/cli.py",
    CodeEdit="""
import argparse
import asyncio
import logging
from pathlib import Path
from .services.orchestrator import VideoOrchestrator
from .infrastructure.ffmpeg import FFmpegWrapper
from .infrastructure.resources import ResourceManager
from .services.detection import DetectionService
from .services.segmentation import SegmentationService
from .services.encoding.dolby_vision import DolbyVisionEncoder
from .services.encoding.svt import SVTEncoder

async def main():
    parser = argparse.ArgumentParser()
    # Add arguments
    args = parser.parse_args()

    # Setup services
    ffmpeg = FFmpegWrapper()
    resources = ResourceManager()
    detection = DetectionService(ffmpeg)
    segmentation = SegmentationService(ffmpeg, resources)
    
    # Select encoder based on detection
    orchestrator = VideoOrchestrator(
        detection=detection,
        segmentation=segmentation,
        encoding=None,  # Set based on detection
        resources=resources
    )

    # Process video
    success = await orchestrator.process_video(
        input_path=Path(args.input),
        output_path=Path(args.output)
    )
    return 0 if success else 1

if __name__ == "__main__":
    asyncio.run(main())
""",
    CodeMarkdownLanguage="python",
    Instruction="Update CLI to use new architecture",
    Blocking=true
)
```

## Phase 8: Testing and Validation

### 8.1 Create Test Directory
```python
# Create test structure
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/tests/__init__.py",
    CodeContent="",
    EmptyFile=true
)

# Create test utilities
write_to_file(
    TargetFile="/home/ken/projects/encodeworkflow/python/drapto/tests/utils.py",
    CodeContent="""
from pathlib import Path
from typing import Optional

class TestResources:
    def __init__(self):
        self.test_files = {
            "dv": Path("tests/data/dolby_vision.mp4"),
            "sdr": Path("tests/data/standard.mp4")
        }

class MockFFmpeg:
    def __init__(self):
        self.commands = []

    async def run_command(self, args):
        self.commands.append(args)
        return ""
""",
    EmptyFile=false
)
```

## Implementation Notes

### Each Phase
1. Use `grep_search` to find affected code
2. Use `view_file` to examine implementations
3. Use `write_to_file` for new files
4. Use `edit_file` for updates

### Validation Steps
1. After each file creation/modification:
   - Check imports resolve
   - Verify syntax
   - Check type hints

2. After each phase:
   - Run existing tests
   - Verify no regressions
   - Check resource cleanup

### Rollback Strategy
1. Keep original files until new code is verified
2. Use version control for safety
3. Implement one component at a time
4. Validate each step before proceeding
