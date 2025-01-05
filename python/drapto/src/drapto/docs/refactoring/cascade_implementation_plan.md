# Drapto AI-Assisted Refactoring Plan

## Overview
This plan is designed for implementation by an AI code assistant. Each step is structured to:
- Maintain system stability during changes
- Allow validation between steps
- Support automatic rollback if needed
- Enable incremental feature deployment

## AI Assistant Guidelines

### Core Principles
1. **Atomic Changes**:
   - Make one logical change at a time
   - Keep changes small and focused
   - Ensure each change can be validated independently
   - Maintain working state between changes

2. **Tool Usage**:
   - Use `codebase_search` for understanding code context
   - Use `grep_search` for finding specific patterns
   - Use `view_file` to examine full implementations
   - Use `edit_file` for precise, minimal changes
   - Use `write_to_file` for new components

3. **Error Prevention**:
   - Validate inputs before processing
   - Add comprehensive error handling
   - Include type hints for all parameters
   - Add assertions for critical assumptions

4. **Code Quality**:
   - Follow PEP 8 style guide
   - Add detailed docstrings
   - Use type hints consistently
   - Keep functions focused and small
   - Use descriptive variable names

5. **Testing Strategy**:
   - Write tests before implementation
   - Include unit tests for components
   - Add integration tests for workflows
   - Test error cases explicitly
   - Verify resource cleanup

6. **Safety Measures**:
   - Use feature flags for new code
   - Log all significant operations
   - Add validation between steps
   - Implement rollback mechanisms
   - Monitor system resources

7. **Documentation**:
   - Update docs with each change
   - Add inline code comments
   - Document error cases
   - Include usage examples
   - Note any limitations

### Implementation Process
For each change:

1. **Analysis**:
   ```python
   # First, understand the context
   results = codebase_search(
       Query="relevant functionality",
       TargetDirectories=["/path/to/code"]
   )
   
   # Then, find specific implementations
   matches = grep_search(
       SearchDirectory="/path/to/code",
       Query="specific pattern",
       MatchPerLine=True,
       Includes=["*.py"],
       CaseInsensitive=False
   )
   ```

2. **Implementation**:
   ```python
   # Create new file with proper structure
   write_to_file(
       TargetFile="/path/to/new/file.py",
       CodeContent="""
       \"\"\"Module docstring with purpose.\"\"\"
       from typing import Optional, List
       
       class NewComponent:
           \"\"\"Class docstring with details.\"\"\"
           def __init__(self) -> None:
               self._logger = logging.getLogger(__name__)
       """,
       EmptyFile=False
   )
   
   # Make precise edits
   edit_file(
       TargetFile="/path/to/existing/file.py",
       CodeEdit="""
       {{ ... }}
       def updated_function(new_param: str) -> bool:
           \"\"\"Function docstring with changes.\"\"\"
       {{ ... }}
       """,
       Instruction="Update function signature",
       Blocking=True
   )
   ```

3. **Validation**:
   ```python
   # Run tests
   run_command(
       Command="pytest",
       ArgsList=["tests/", "-v"],
       Blocking=True
   )
   
   # Check typing
   run_command(
       Command="mypy",
       ArgsList=["src/"],
       Blocking=True
   )
   ```

### Error Handling
Always implement proper error handling:

```python
class SafeComponent:
    """Example of proper error handling."""
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        
    async def process(self, input_path: Path) -> bool:
        try:
            self._logger.info(f"Processing {input_path}")
            if not input_path.exists():
                raise FileNotFoundError(f"Input not found: {input_path}")
                
            # Core logic here
            return True
            
        except FileNotFoundError as e:
            self._logger.error(f"Input error: {e}")
            raise
            
        except Exception as e:
            self._logger.error(f"Unexpected error: {e}")
            raise RuntimeError(f"Processing failed: {e}")
```

### Feature Flags
Use feature flags for safe deployment:

```python
class FeatureFlags:
    """Manage feature rollout."""
    
    def __init__(self) -> None:
        self._flags = {
            "new_detection": False,
            "new_segmentation": False,
            "new_encoding": False,
            "new_audio": False,
            "new_track_handling": False
        }
        self._logger = logging.getLogger(__name__)
        
    def is_enabled(self, flag: str) -> bool:
        enabled = self._flags.get(flag, False)
        self._logger.debug(f"Feature flag {flag}: {enabled}")
        return enabled

## AI Assistant Guidelines

The AI assistant will:

1. **Code Changes**:
   - Create new files in isolation
   - Add comprehensive type hints
   - Include detailed docstrings
   - Follow PEP 8 style guide

2. **Testing**:
   - Write tests before implementation
   - Include both unit and integration tests
   - Add performance benchmarks
   - Validate against old implementation

3. **Safety**:
   - Enable feature flags gradually
   - Log all significant operations
   - Handle all potential errors
   - Provide rollback mechanisms

4. **Documentation**:
   - Update relevant documentation
   - Add inline code comments
   - Document any caveats or limitations
   - Include usage examples

5. **Validation**:
   - Run existing test suite
   - Verify resource cleanup
   - Check error handling
   - Monitor performance impact

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

### Migration Strategy

1. **Feature Flags**
   - Add flag configuration
   - Implement toggles
   - Create monitoring
   - Add metrics

2. **Validation**
   - Add quality checks
   - Create comparisons
   - Implement metrics
   - Add reporting

3. **Documentation**
   - Update guides
   - Add API docs
   - Create examples
   - Add troubleshooting

## Phase 0: Preparation

### 0.1 Initial Analysis
```python
# Step 1: Analyze existing codebase structure
def analyze_codebase():
    """Find all relevant Python files and their relationships."""
    # Search for Python files
    python_files = find_files("**/*.py")
    
    # Find main entry points
    entry_points = grep_search("if __name__ == '__main__'")
    
    # Locate core classes
    core_classes = grep_search("class.*Processor|class.*Handler|class.*Manager")

# Step 2: Create new structure
def setup_structure():
    """Create new module structure."""
    create_dirs = [
        "core/",
        "services/",
        "infrastructure/"
    ]
    for dir in create_dirs:
        Path(dir).mkdir(exist_ok=True)
```

### 0.2 Test Infrastructure
```python
# Step 1: Basic test infrastructure
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

# Step 2: Track-specific tests
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

### 0.3 Safety Infrastructure
```python
# Step 1: Logging setup
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

# Step 2: Feature flags
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

# Step 3: Performance monitoring
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

## Phase 1: Core Domain Models

### 1.1 Create Basic Models
```python
# Step 1: Video metadata model
@dataclass
class VideoMetadata:
    """Core video properties."""
    path: Path
    width: int
    height: int
    is_dolby_vision: bool
    frame_rate: float
    duration: float

# Step 2: Audio metadata model
@dataclass
class AudioMetadata:
    """Audio stream properties."""
    channels: int
    codec: str
    bitrate: Optional[int]
    layout: str

# Step 3: Track metadata model
@dataclass
class TrackMetadata:
    """Complete media track information."""
    video: VideoMetadata
    audio: List[AudioMetadata]
    subtitles: List[str]
    has_chapters: bool
```

### 1.2 Create Path-Specific Models
```python
# Step 1: Dolby Vision context
@dataclass
class DolbyVisionContext:
    """Dolby Vision encoding parameters."""
    metadata: TrackMetadata
    crf: int
    preset: int
    hw_accel: Optional[str]

# Step 2: Chunked encoding context
@dataclass
class ChunkedEncodingContext:
    """Chunked encoding parameters."""
    metadata: TrackMetadata
    target_vmaf: float
    segment_length: int
    sample_count: int
```

## Phase 2: Infrastructure

### 2.1 FFmpeg Integration
```python
# Step 1: Basic FFmpeg wrapper
class FFmpegWrapper:
    def __init__(self, binary_path: Path):
        self.binary_path = binary_path
        
    async def probe_file(self, input_path: Path) -> dict:
        pass

# Step 2: Add hardware acceleration
class HardwareAcceleration:
    def detect_support(self) -> Optional[str]:
        pass
        
    def get_options(self) -> List[str]:
        pass

# Step 3: Add track extraction
class TrackExtractor:
    def extract_audio(self, input_path: Path, output_path: Path) -> bool:
        pass
        
    def extract_subtitles(self, input_path: Path, output_dir: Path) -> List[Path]:
        pass
```

## Phase 3: Services

### 3.1 Detection Services
```python
# Step 1: Basic video analysis
class VideoAnalyzer:
    def analyze_metadata(self, path: Path) -> VideoMetadata:
        pass

# Step 2: Audio analysis
class AudioAnalyzer:
    def analyze_streams(self, path: Path) -> List[AudioMetadata]:
        pass

# Step 3: Track analysis
class TrackAnalyzer:
    def analyze_all(self, path: Path) -> TrackMetadata:
        pass
```

### 3.2 Encoding Services
```python
# Step 1: Audio encoding
class AudioEncoder:
    def encode_opus(self, input_path: Path, output_path: Path, metadata: AudioMetadata) -> bool:
        pass

# Step 2: Dolby Vision encoding
class DolbyVisionEncoder:
    def encode(self, context: DolbyVisionContext) -> bool:
        pass

# Step 3: Chunked encoding
class ChunkedEncoder:
    def encode_segment(self, segment: Path, context: ChunkedEncodingContext) -> bool:
        pass
```

## Phase 4: Resource Management

### 4.1 Work Directory Management
```python
# Step 1: Basic directory structure
class WorkDirectoryManager:
    def create_structure(self) -> Dict[str, Path]:
        pass

# Step 2: Resource cleanup
class ResourceCleaner:
    def cleanup(self, work_dirs: Dict[str, Path]) -> None:
        pass
```

### 4.2 Track Management
```python
# Step 1: Track extraction
class TrackManager:
    def extract_tracks(self, input_path: Path, work_dirs: Dict[str, Path]) -> None:
        pass

# Step 2: Track muxing
class TrackMuxer:
    def mux_tracks(self, tracks: Dict[str, Path], output_path: Path) -> bool:
        pass
```

## Phase 5: Integration

### 5.1 Path-Specific Processors
```python
# Step 1: Dolby Vision processor
class DolbyVisionProcessor:
    def process(self, context: DolbyVisionContext) -> bool:
        pass

# Step 2: Chunked encoding processor
class ChunkedProcessor:
    def process(self, context: ChunkedEncodingContext) -> bool:
        pass
```

### 5.2 Main Processor
```python
# Step 1: Path selection
class PathSelector:
    def select_path(self, metadata: TrackMetadata) -> str:
        pass

# Step 2: Main processor
class VideoProcessor:
    def process_video(self, input_path: Path, output_path: Path) -> bool:
        pass
```

## Phase 6: Orchestration

### 6.1 Create Orchestrator
```python
# Create orchestrator
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
