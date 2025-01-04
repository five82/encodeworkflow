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
7. Scattered validation logic
8. Mixed resource management
9. Unclear state transitions
10. Limited error recovery mechanisms

## Workflow-Driven Insights

### 1. Process Boundaries
- Clear separation needed between detection, segmentation, and encoding
- Each process requires dedicated error handling
- Natural transaction boundaries exist between stages

### 2. State Management
- Need explicit state tracking between processes
- Clear state validation at boundaries
- Transaction-like state changes

### 3. Error Recovery
- Implement recovery points at natural workflow boundaries
- Add rollback capabilities
- Separate error handling from business logic

### 4. Configuration Management
- Stronger validation between dependent settings
- Domain-specific configuration validation
- Clearer configuration hierarchies

### 5. Process Isolation
- Separate strategies for Dolby Vision and SVT-AV1 paths
- Clear boundaries between shared and path-specific components
- Isolated resource management

## Proposed Architecture

### 1. Domain-Driven Design Structure
```
drapto/
├── core/                 # Core domain logic
│   ├── models.py        # Domain models
│   └── interfaces.py    # Abstract interfaces
├── services/            # Implementation of core interfaces
│   ├── detection/       # Video analysis services
│   ├── encoding/        # Encoding services
│   ├── audio/          # Audio processing
│   └── segmentation/   # Video segmentation
├── infrastructure/      # Technical implementations
│   ├── ffmpeg/         # FFmpeg integration
│   ├── filesystem/     # File operations
│   └── resources/      # Resource management
├── state/              # State management
│   ├── models.py       # State models
│   └── transitions.py  # State machines
├── config/             # Configuration management
└── cli/               # Command line interface
```

### 2. Service Interfaces
```python
# Core service interfaces
class IDetectionService(Protocol):
    def analyze_video(self, input_path: Path) -> VideoAnalysis: ...
    def detect_dolby_vision(self, input_path: Path) -> bool: ...
    def detect_crop(self, input_path: Path) -> Optional[CropParameters]: ...

class IEncodingService(Protocol):
    def encode(self, context: EncodingContext) -> None: ...
    def validate_output(self, context: ValidationContext) -> bool: ...

class IStateManager(Protocol):
    def transition(self, state: ProcessingState) -> None: ...
    def validate_transition(self, from_state: ProcessingState, to_state: ProcessingState) -> bool: ...
```

### 3. State Management
```python
# State tracking
class ProcessingState:
    def __init__(self):
        self.stage: ProcessingStage
        self.context: ProcessingContext
        self.resources: ResourceState
        self.validation: ValidationState

class StateTransition:
    def __init__(self, from_state: ProcessingState, to_state: ProcessingState):
        self.validate()
        self.execute()
        self.commit()
```

### 4. Resource Management
```python
# Resource handling
class ResourceManager:
    def __init__(self):
        self.active_resources: Set[Resource]
        self.cleanup_handlers: Dict[Resource, CleanupHandler]

    def acquire(self, resource: Resource) -> None: ...
    def release(self, resource: Resource) -> None: ...
    def cleanup(self) -> None: ...
```

## Implementation Strategy

### Phase 1: Core Infrastructure
1. Create new directory structure
2. Define core interfaces
3. Implement state management
4. Add resource management

### Phase 2: Service Migration
1. Create detection services
2. Implement encoding services
3. Add segmentation services
4. Create audio services

### Phase 3: Process Isolation
1. Separate Dolby Vision path
2. Implement SVT-AV1 path
3. Add shared components
4. Implement validation chains

### Phase 4: State and Recovery
1. Add state tracking
2. Implement recovery points
3. Add validation boundaries
4. Create cleanup handlers

## Migration Steps

1. **Create New Structure**
   - Set up directory layout
   - Add new interfaces
   - Create base classes

2. **Migrate Core Logic**
   - Move detection logic
   - Refactor encoding paths
   - Separate validation

3. **Add New Features**
   - State management
   - Resource tracking
   - Recovery mechanisms

4. **Update Integration**
   - Modify CLI interface
   - Update configuration
   - Add new validators

## Testing Strategy

1. **Unit Tests**
   - Service-level tests
   - State transition tests
   - Validation tests

2. **Integration Tests**
   - Process flow tests
   - Resource management
   - Error recovery

3. **System Tests**
   - End-to-end workflows
   - Performance tests
   - Resource usage

## Benefits
1. Clearer process boundaries
2. Better state management
3. Improved error recovery
4. Isolated resource handling
5. Stronger validation
6. Better maintainability
7. Easier testing
8. Clearer configuration

## Notes
- Implement changes gradually
- Maintain existing functionality
- Add comprehensive tests
- Document state transitions
- Monitor resource usage
