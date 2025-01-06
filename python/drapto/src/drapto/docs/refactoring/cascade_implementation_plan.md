# Drapto AI-Assisted Refactoring Plan

## Overview
This plan is designed for implementation by an AI code assistant. Each step is structured to:
- Maintain system stability during changes
- Preserve existing functionality
- Enable gradual migration
- Support comprehensive testing

## Implementation Guidelines

1. **Code Changes**:
   - Create new files in isolation
   - Add comprehensive type hints
   - Include detailed docstrings
   - Follow PEP 8 style guide

2. **Testing**:
   - Write tests before implementation
   - Maintain existing test coverage
   - Add regression tests
   - Include performance tests

3. **Documentation**:
   - Update docs with changes
   - Include examples
   - Document limitations
   - Add troubleshooting guides

## Implementation Plan

### Phase 1: Core Architecture

1. **Video Analysis Components**
   - Create stream analysis utilities
   - Add HDR detection
   - Implement black bar detection
   - Add quality settings selection
   - Create hardware detection

2. **Base Classes and Interfaces**
   - Create encoding base classes
   - Define common interfaces
   - Implement factory pattern
   - Add resource monitoring framework

3. **Hardware Support**
   - Add device detection
   - Implement acceleration options
   - Create fallback strategies
   - Add performance monitoring

4. **Resource Management**
   - Add CPU/memory monitoring
   - Implement disk space tracking
   - Create cleanup strategies
   - Add resource optimization

5. **Progress Reporting**
   - Implement logging hierarchy
   - Add progress tracking
   - Create command formatting
   - Define log levels

### Phase 2: Path Implementation

1. **Video Stream Analysis**
   - Add resolution detection
   - Implement HDR analysis
   - Create color space validation
   - Add stream size tracking
   - Implement black bar detection

2. **Dolby Vision Path**
   - Implement metadata handling
   - Add FFmpeg integration
   - Create validation checks
   - Add error recovery
   - Handle HDR requirements

3. **Chunked Encoding Path**
   - Implement segmentation
   - Add parallel processing
   - Create segment validation
   - Add error recovery
   - Handle HDR segments

4. **Common Components**
   - Implement audio processing
   - Add subtitle handling
   - Create muxing logic
   - Add validation suite

### Phase 3: Resource Management

1. **Monitoring**
   - Implement CPU tracking
   - Add memory monitoring
   - Create disk space checks
   - Add network monitoring

2. **Optimization**
   - Add resource allocation
   - Implement cleanup
   - Create recovery strategies
   - Add performance tracking

### Phase 4: Error Handling

1. **Recovery Strategies**
   - Implement retries
   - Add state recovery
   - Create rollback logic
   - Add validation checks

2. **Logging**
   - Add structured logging
   - Implement error tracking
   - Create debug output
   - Add performance metrics

### Phase 5: Testing

1. **Unit Tests**
   - Add component tests
   - Create mock interfaces
   - Implement assertions
   - Add coverage reports

2. **Integration Tests**
   - Add workflow tests
   - Create benchmarks
   - Implement validation
   - Add performance tests

## Directory Structure

The following directory structure aligns with our implementation plan and provides clear separation of concerns:

```
python/drapto/
├── pyproject.toml
├── requirements.txt
├── README.md
├── src/
│   └── drapto/
│       ├── __init__.py
│       ├── cli.py                 # Command-line interface
│       ├── config/
│       │   ├── __init__.py
│       │   ├── config.py         # Configuration models
│       │   └── default_config.py # Default settings
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── base.py          # Base classes and interfaces
│       │   └── factory.py       # Factory pattern implementations
│       │
│       ├── encoding/
│       │   ├── __init__.py
│       │   ├── analysis/
│       │   │   ├── __init__.py
│       │   │   ├── video.py     # Video analysis
│       │   │   ├── audio.py     # Audio analysis
│       │   │   └── metadata.py  # Metadata extraction
│       │   │
│       │   ├── paths/
│       │   │   ├── __init__.py
│       │   │   ├── chunked.py   # Chunked encoding path
│       │   │   └── dolby.py     # Dolby Vision path
│       │   │
│       │   └── processors/
│       │       ├── __init__.py
│       │       ├── audio.py     # Audio processing
│       │       ├── subtitle.py  # Subtitle handling
│       │       └── muxer.py     # Muxing logic
│       │
│       ├── infrastructure/
│       │   ├── __init__.py
│       │   ├── ffmpeg/
│       │   │   ├── __init__.py
│       │   │   └── wrapper.py   # FFmpeg Python bindings
│       │   │
│       │   ├── hardware/
│       │   │   ├── __init__.py
│       │   │   └── acceleration.py  # Hardware acceleration
│       │   │
│       │   └── monitoring/
│       │       ├── __init__.py
│       │       ├── resources.py  # Resource monitoring
│       │       └── performance.py # Performance tracking
│       │
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── formatting.py    # Output formatting
│       │   ├── validation.py    # Input validation
│       │   └── logging.py       # Logging configuration
│       │
│       └── workflow/
│           ├── __init__.py
│           ├── orchestrator.py   # Main workflow orchestrator
│           ├── path_manager.py   # Path management
│           └── work_manager.py   # Work directory management
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── data/                    # Test data files
    │   ├── dolby_vision/
    │   └── standard/
    │
    ├── unit/
    │   ├── __init__.py
    │   ├── test_config/
    │   ├── test_core/
    │   ├── test_encoding/
    │   ├── test_infrastructure/
    │   └── test_workflow/
    │
    └── integration/
        ├── __init__.py
        └── test_paths/          # End-to-end path tests
```

## Migration Plan

The migration to the new directory structure will be done in phases to maintain stability and ensure no functionality is lost.

### Phase 1: Core Infrastructure

1. **Create New Directory Structure**
   - Create all new directories as shown above
   - Add `__init__.py` files to each directory
   - Create placeholder files with docstrings

2. **Move Configuration**
   - Move `config.py` → `config/config.py`
   - Move `default_config.py` → `config/default_config.py`
   - Update imports in all files referencing these modules

3. **Setup Core Module**
   - Move base classes from `encoding/base.py` → `core/base.py`
   - Move factory from `encoding/factory.py` → `core/factory.py`
   - Update all imports

### Phase 2: Encoding Components

1. **Reorganize Analysis**
   - Move `video_analysis.py` → `encoding/analysis/video.py`
   - Split audio analysis from `audio_processor.py` → `encoding/analysis/audio.py`
   - Create `encoding/analysis/metadata.py`

2. **Setup Encoding Paths**
   - Move `chunked.py` → `encoding/paths/chunked.py`
   - Move `dolby_vision.py` → `encoding/paths/dolby.py`
   - Update imports and references

3. **Create Processors**
   - Move audio processing from `audio_processor.py` → `encoding/processors/audio.py`
   - Create `encoding/processors/subtitle.py`
   - Create `encoding/processors/muxer.py`

### Phase 3: Infrastructure

1. **FFmpeg Integration**
   - Create `infrastructure/ffmpeg/wrapper.py`
   - Move FFmpeg-related code from various files
   - Update all FFmpeg calls to use new wrapper

2. **Hardware Support**
   - Create `infrastructure/hardware/acceleration.py`
   - Move hardware detection and acceleration code
   - Update references

3. **Monitoring**
   - Move monitoring code to `infrastructure/monitoring/`
   - Split into resources.py and performance.py
   - Update all monitoring calls

### Phase 4: Utils and Workflow

1. **Utils Organization**
   - Move `formatting.py` → `utils/formatting.py`
   - Move `validation.py` → `utils/validation.py`
   - Create `utils/logging.py`

2. **Workflow Components**
   - Move `path_manager.py` → `workflow/path_manager.py`
   - Move `work_manager.py` → `workflow/work_manager.py`
   - Create `workflow/orchestrator.py`

### Phase 5: Testing Structure

1. **Setup Test Directories**
   - Create test directory structure
   - Move existing tests to appropriate locations
   - Create `conftest.py` with common fixtures

2. **Add Test Data**
   - Create test data directories
   - Add sample files for both paths
   - Update test paths

3. **Update Test Imports**
   - Update all test imports to match new structure
   - Verify all tests pass

### Migration Guidelines

1. **For Each Phase**
   - Create new directories first
   - Move files one at a time
   - Update imports immediately
   - Run tests after each move
   - Commit after each successful move

2. **Testing**
   - Run full test suite after each file move
   - Add new tests for any new components
   - Verify no functionality is lost

3. **Documentation**
   - Update docstrings to reflect new locations
   - Update import examples in documentation
   - Update README with new structure

4. **Version Control**
   - Create feature branch for migration
   - Commit each file move separately
   - Include clear commit messages
   - Create PR for review

### Rollback Plan

1. **Preparation**
   - Create backup branch before starting
   - Document all file movements
   - Keep original files until verified

2. **Monitoring**
   - Monitor test results after each change
   - Watch for import errors
   - Check for performance impacts

3. **Recovery**
   - Revert to backup branch if needed
   - Restore individual files if necessary
   - Roll back one phase at a time

## Technical Implementation Details

This section provides detailed technical specifications and code examples for implementing each phase.

### Core Domain Models

```python
# Video metadata model
@dataclass
class VideoMetadata:
    """Core video properties."""
    path: Path
    width: int
    height: int
    is_dolby_vision: bool
    frame_rate: float
    duration: float

# Audio metadata model
@dataclass
class AudioMetadata:
    """Audio stream properties."""
    channels: int
    codec: str
    bitrate: Optional[int]
    layout: str

# Track metadata model
@dataclass
class TrackMetadata:
    """Complete media track information."""
    video: VideoMetadata
    audio: List[AudioMetadata]
    subtitles: List[str]
    has_chapters: bool

# Encoding contexts
@dataclass
class DolbyVisionContext:
    """Dolby Vision encoding parameters."""
    metadata: TrackMetadata
    crf: int
    preset: int
    hw_accel: Optional[str]

@dataclass
class ChunkedEncodingContext:
    """Chunked encoding parameters."""
    metadata: TrackMetadata
    target_vmaf: float
    segment_length: int
    sample_count: int
```

### Infrastructure Components

```python
# FFmpeg integration
class FFmpegWrapper:
    def __init__(self, binary_path: Path):
        self.binary_path = binary_path
        
    async def probe_file(self, input_path: Path) -> dict:
        pass

class HardwareAcceleration:
    def detect_support(self) -> Optional[str]:
        pass
        
    def get_options(self) -> List[str]:
        pass

class TrackExtractor:
    def extract_audio(self, input_path: Path, output_path: Path) -> bool:
        pass
        
    def extract_subtitles(self, input_path: Path, output_dir: Path) -> List[Path]:
        pass
```

### Safety Infrastructure

```python
# Logging setup
def setup_logging():
    """Configure comprehensive logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Add file handler for debugging
    fh = logging.FileHandler('drapto.log')
    fh.setLevel(logging.DEBUG)
    logging.getLogger('').addHandler(fh)

# Feature flags
class FeatureFlags:
    """Safe feature rollout control."""
    def __init__(self):
        self._flags = {
            "new_detection": False,
            "new_segmentation": False,
            "new_encoding": False,
            "new_audio": False,
            "new_track_handling": False
        }
    
    def is_enabled(self, flag: str) -> bool:
        return self._flags.get(flag, False)
        
    def enable(self, flag: str):
        if flag in self._flags:
            self._flags[flag] = True

# Performance monitoring
class PerformanceMonitor:
    """Track execution time of components."""
    def __init__(self):
        self.start_time = None
        self.checkpoints = {}
        
    def start(self):
        self.start_time = time.time()
        
    def checkpoint(self, name: str):
        self.checkpoints[name] = time.time() - self.start_time
```

### Test Infrastructure

```python
# Basic workflow tests
class TestCurrentWorkflow:
    """Baseline tests to ensure no regression."""
    async def test_basic_encoding(self):
        """Test current end-to-end flow."""
        input_path = Path("test_data/sample.mkv")
        output_path = Path("test_output/encoded.mkv")
        processor = VideoProcessor()
        await processor.process_video(input_path, output_path)
        assert output_path.exists()
        
    async def test_dolby_vision(self):
        """Test Dolby Vision flow."""
        input_path = Path("test_data/dolby_vision.mkv")
        output_path = Path("test_output/dv_encoded.mkv")
        processor = VideoProcessor()
        await processor.process_video(input_path, output_path)
        assert output_path.exists()

# Track-specific tests
class TestTrackHandling:
    """Tests for audio, subtitle, and chapter handling."""
    async def test_audio_processing(self):
        """Test audio extraction and encoding."""
        pass
        
    async def test_subtitle_preservation(self):
        """Test subtitle track handling."""
        pass
        
    async def test_chapter_preservation(self):
        """Test chapter preservation."""
        pass
```

## Implementation Notes

### Each Phase
1. Use `grep_search` to find affected code
2. Use `view_file` to examine implementations
3. Use `write_to_file` for new files
4. Use `edit_file` for updates

### Testing Requirements
1. Add unit tests for each component
2. Include integration tests for workflows
3. Add performance benchmarks
4. Verify error handling

### Documentation Requirements
1. Update API documentation
2. Add usage examples
3. Include troubleshooting guides
4. Document performance characteristics
