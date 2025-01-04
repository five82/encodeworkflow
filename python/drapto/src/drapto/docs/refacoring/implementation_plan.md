# Drapto Incremental Refactoring Plan

## Overview
This document outlines a step-by-step plan for refactoring Drapto while maintaining functionality throughout the process. Each phase is designed to be independently deployable with minimal risk.

## Phase 0: Preparation (1-2 weeks)

### 0.1 Test Coverage
1. Add integration tests for current functionality
   ```python
   class TestCurrentWorkflow:
       async def test_basic_encoding(self):
           # Test current end-to-end flow
           pass
       
       async def test_dolby_vision(self):
           # Test current DV flow
           pass
   ```

### 0.2 Monitoring
1. Add basic logging
   ```python
   import logging
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
   ```

### 0.3 Feature Flags
1. Implement feature flag system
   ```python
   class FeatureFlags:
       def __init__(self):
           self.flags = {
               "new_detection": False,
               "new_segmentation": False,
               "new_encoding": False
           }
   ```

## Phase 1: Core Infrastructure (2-3 weeks)

### 1.1 Directory Structure
```
drapto/
├── core/
│   ├── __init__.py
│   ├── models.py        # Domain models
│   └── interfaces.py    # Core interfaces
├── services/
│   ├── __init__.py
│   └── legacy/          # Current implementation
├── infrastructure/
│   ├── __init__.py
│   └── ffmpeg/
└── utils/
    ├── __init__.py
    └── logging.py
```

### 1.2 Basic Interfaces
```python
# core/interfaces.py
from typing import Protocol, List
from pathlib import Path

class IVideoProcessor(Protocol):
    async def process_video(self, input_path: Path, output_path: Path) -> None: ...

class IDetectionService(Protocol):
    async def analyze_video(self, input_path: Path) -> VideoAnalysis: ...
```

### 1.3 Move Current Code
1. Move existing code to `services/legacy/`
2. Create facade around legacy code
3. No functional changes yet

## Phase 2: Detection Service (2-3 weeks)

### 2.1 New Detection Service
```python
# services/detection/service.py
class DetectionService:
    def __init__(self, ffmpeg: IFFmpeg):
        self._ffmpeg = ffmpeg
        self._logger = logging.getLogger(__name__)

    async def analyze_video(self, input_path: Path) -> VideoAnalysis:
        # New implementation
        pass
```

### 2.2 Parallel Implementation
1. Implement new service
2. Run in parallel with old code
3. Compare results
4. Log discrepancies

### 2.3 Gradual Rollout
1. Add feature flag
2. Monitor results
3. Validate output
4. Roll back capability

## Phase 3: State Management (2-3 weeks)

### 3.1 State Infrastructure
```python
# core/state.py
class ProcessingState:
    def __init__(self):
        self.stage: ProcessingStage
        self.context: Dict[str, Any]
        self.resources: Set[Resource]

class StateManager:
    def __init__(self):
        self._states: Dict[str, ProcessingState] = {}
        self._logger = logging.getLogger(__name__)

    async def transition(self, job_id: str, new_stage: ProcessingStage) -> None:
        # Implementation
        pass
```

### 3.2 Integration
1. Add state tracking to legacy code
2. No behavioral changes
3. Just monitoring

## Phase 4: Resource Management (2-3 weeks)

### 4.1 Resource Tracking
```python
# infrastructure/resources.py
class ResourceManager:
    def __init__(self):
        self._active: Set[Resource] = set()
        self._logger = logging.getLogger(__name__)

    async def acquire(self, resource: Resource) -> None:
        # Implementation
        pass

    async def release(self, resource: Resource) -> None:
        # Implementation
        pass
```

### 4.2 Integration
1. Wrap current resource usage
2. Monitor leaks
3. Add cleanup handlers

## Phase 5: Segmentation Service (2-3 weeks)

### 5.1 New Implementation
```python
# services/segmentation/service.py
class SegmentationService:
    def __init__(self, 
                 ffmpeg: IFFmpeg,
                 resource_manager: ResourceManager):
        self._ffmpeg = ffmpeg
        self._resources = resource_manager
        self._logger = logging.getLogger(__name__)

    async def segment_video(self, 
                          input_path: Path,
                          work_dir: Path) -> List[Path]:
        # New implementation
        pass
```

### 5.2 Parallel Running
1. Implement new service
2. Run alongside old code
3. Compare results
4. Monitor performance

## Phase 6: Encoding Service (3-4 weeks)

### 6.1 Path-Specific Services
```python
# services/encoding/dolby_vision.py
class DolbyVisionEncoder:
    async def encode(self, context: EncodingContext) -> None:
        # Implementation
        pass

# services/encoding/svt.py
class SVTEncoder:
    async def encode(self, context: EncodingContext) -> None:
        # Implementation
        pass
```

### 6.2 Gradual Migration
1. One path at a time
2. Start with SVT-AV1
3. Then Dolby Vision
4. Careful validation

## Phase 7: New Pipeline (2-3 weeks)

### 7.1 Orchestrator
```python
# services/orchestrator.py
class VideoOrchestrator:
    def __init__(self,
                 detection: IDetectionService,
                 segmentation: ISegmentationService,
                 encoding: IEncodingService,
                 state_manager: StateManager):
        self._detection = detection
        self._segmentation = segmentation
        self._encoding = encoding
        self._state = state_manager
        self._logger = logging.getLogger(__name__)

    async def process_video(self,
                          input_path: Path,
                          output_path: Path) -> None:
        # New implementation
        pass
```

### 7.2 Rollout Strategy
1. Start with non-critical workloads
2. Gradually increase traffic
3. Monitor closely
4. Keep rollback path

## Phase 8: CLI Updates (1-2 weeks)

### 8.1 New Interface
```python
# cli/main.py
class CLI:
    def __init__(self):
        self._orchestrator = VideoOrchestrator()
        self._logger = logging.getLogger(__name__)

    async def run(self, args: argparse.Namespace) -> int:
        # New implementation
        pass
```

### 8.2 Deployment
1. Update CLI gradually
2. Maintain backwards compatibility
3. Add new options
4. Update documentation

## Phase 9: Cleanup (1-2 weeks)

### 9.1 Remove Legacy Code
1. Remove feature flags
2. Clean up old implementations
3. Update documentation
4. Archive reference code

### 9.2 Final Validation
1. Full test suite
2. Performance validation
3. Resource usage check
4. Documentation review

## Rollback Strategy

### Feature Flags
```python
class FeatureFlags:
    def __init__(self):
        self._flags = {
            "use_new_detection": False,
            "use_new_segmentation": False,
            "use_new_encoding": False,
            "use_new_pipeline": False
        }
    
    def is_enabled(self, flag: str) -> bool:
        return self._flags.get(flag, False)
```

### Monitoring
```python
class PerformanceMonitor:
    def __init__(self):
        self._metrics = MetricsCollector()
        self._logger = logging.getLogger(__name__)

    def record_metric(self, name: str, value: float):
        self._metrics.record(name, value)
        if self._should_alert(name, value):
            self._logger.warning(f"Metric {name} exceeded threshold")
```

### Recovery
```python
class RollbackManager:
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    async def rollback_feature(self, feature: str) -> None:
        # Disable feature flag
        # Restore old implementation
        # Log rollback
        pass
```

## Timeline
- Total Duration: 17-23 weeks
- Each phase is independently deployable
- Phases can overlap when safe
- Built-in validation points
- Continuous monitoring

## Success Metrics
1. No production disruption
2. Equal or better performance
3. Improved resource usage
4. Better error handling
5. Cleaner codebase

## Risk Mitigation
1. Feature flags for control
2. Parallel implementations
3. Comprehensive monitoring
4. Clear rollback paths
5. Regular validation
