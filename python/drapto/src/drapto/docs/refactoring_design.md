# Drapto Refactoring Design Document

## Overview
This document outlines a comprehensive refactoring plan for the Drapto video processing system. The goal is to improve code organization, reduce coupling between components, and make the system more maintainable without changing any existing functionality.

## Current Architecture
- **Entry Point**: `cli.py` handles command line interface and argument parsing
- **Core Components**:
  - `VideoProcessor`: Main orchestrator class
  - `SegmentHandler`: Manages video segmentation
  - `AudioProcessor`: Handles audio processing
  - `VideoEncoder`: Handles video encoding
  - `WorkDirectoryManager`: Manages temporary work directories
  - `PathManager`: Handles path resolution and validation
  - `EncodingConfig`: Configuration management

## Issues Identified
1. High coupling between components
2. Large monolithic classes (especially VideoProcessor)
3. Mixed responsibilities in some modules
4. Direct dependencies between components
5. Lack of clear interfaces between components
6. Configuration is tightly coupled with implementation

## Proposed Architecture

### 1. Domain-Driven Design Structure
```
drapto/
├── core/              # Core domain logic
│   ├── models.py      # Domain models
│   └── interfaces.py  # Abstract interfaces
├── services/          # Implementation of core interfaces
│   ├── encoding/
│   ├── audio/
│   └── segmentation/
├── infrastructure/    # Technical implementations
│   ├── ffmpeg/
│   └── filesystem/
├── config/           # Configuration management
└── cli/             # Command line interface
```

### 2. Interface Definitions
```python
# interfaces.py
class IVideoEncoder(Protocol):
    def encode_segment(self, input_path: Path, output_path: Path) -> None: ...
    def analyze_quality(self, source: Path, encoded: Path) -> float: ...

class ISegmentHandler(Protocol):
    def segment_video(self, input_path: Path, output_dir: Path) -> List[Path]: ...
    def concatenate_segments(self, segments: List[Path], output_path: Path) -> None: ...
```

### 3. Factory Pattern
```python
class ProcessorFactory:
    def create_video_processor(self, config: Config) -> IVideoProcessor: ...
    def create_audio_processor(self, config: Config) -> IAudioProcessor: ...
```

### 4. Example Refactored Component
```python
# core/interfaces.py
from typing import Protocol, List
from pathlib import Path

class IVideoProcessor(Protocol):
    def process_video(self, input_path: Path, output_path: Path) -> None: ...

class IEncodingService(Protocol):
    def encode(self, input_path: Path, output_path: Path) -> None: ...
    def analyze_quality(self, source: Path, encoded: Path) -> float: ...

# services/encoding/encoder.py
class EncodingService:
    def __init__(self, config: EncodingConfig, ffmpeg: IFFmpegWrapper):
        self._config = config
        self._ffmpeg = ffmpeg

    def encode(self, input_path: Path, output_path: Path) -> None:
        # Implementation

# services/processor.py
class VideoProcessor:
    def __init__(
        self,
        encoder: IEncodingService,
        segment_handler: ISegmentHandler,
        audio_processor: IAudioProcessor,
        work_manager: IWorkManager
    ):
        self._encoder = encoder
        self._segment_handler = segment_handler
        self._audio_processor = audio_processor
        self._work_manager = work_manager
```

## Implementation Strategy

### Phase 1: Foundation
1. Create new directory structure
2. Define core interfaces in `core/interfaces.py`
3. Create basic test infrastructure

### Phase 2: Component Migration
1. Create new service implementations
2. Gradually move existing code to new structure
3. Implement dependency injection
4. Add unit tests for each component

### Phase 3: Integration
1. Update CLI to use new architecture
2. Add integration tests
3. Implement event system
4. Add error boundaries

## Key Improvements

### 1. Dependency Injection
- Create interfaces for all major components
- Inject dependencies through constructors
- Remove direct component creation

### 2. Configuration Management
- Split configuration into domain-specific configs
- Use composition over inheritance
- Implement validation at config boundaries

### 3. Error Handling
- Create domain-specific exceptions
- Implement error boundaries at service layers
- Add proper error recovery mechanisms

### 4. Testing Improvements
- Create interfaces for external dependencies
- Implement mock services
- Add integration test boundaries

## Benefits
1. More modular and testable code
2. Reduced coupling between components
3. Easier modification of individual components
4. Improved error handling and recovery
5. Better maintainability and extensibility

## Migration Notes
- Implement changes gradually
- Maintain existing functionality throughout
- Add comprehensive tests before refactoring
- Use feature flags if needed for gradual rollout

## Conclusion
This refactoring plan provides a clear path to improving the Drapto codebase while maintaining all existing functionality. The changes focus on better organization, reduced coupling, and improved maintainability through modern software engineering practices.
