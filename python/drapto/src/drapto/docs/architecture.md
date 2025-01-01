# Drapto Architecture

## Overview
Drapto is a video encoding workflow system that processes videos through segmentation, encoding, and quality analysis. This document describes the high-level architecture and component interactions.

## Core Components

### Video Processing Pipeline
```
Input Video → Segmentation → Parallel Encoding → Quality Analysis → Concatenation → Output Video
                   ↓              ↓                     ↓              ↓
             Segment Files → Encoded Files → Quality Metrics → Final Output
```

### Component Responsibilities

1. **Video Processor**
   - Orchestrates the entire encoding process
   - Manages workflow between components
   - Handles error recovery and cleanup

2. **Segment Handler**
   - Splits videos into manageable segments
   - Manages segment metadata
   - Handles segment concatenation

3. **Video Encoder**
   - Performs actual video encoding
   - Manages encoding parameters
   - Handles quality analysis

4. **Audio Processor**
   - Handles audio stream extraction
   - Manages audio encoding
   - Handles audio-video synchronization

5. **Work Manager**
   - Manages temporary work directories
   - Handles cleanup of intermediate files
   - Ensures atomic operations

6. **Path Manager**
   - Handles path resolution and validation
   - Manages file system operations
   - Ensures consistent path handling

## Data Flow
1. CLI receives input/output paths and configuration
2. Path Manager validates and prepares paths
3. Work Manager creates temporary workspace
4. Segment Handler splits input video
5. Video Encoder processes segments in parallel
6. Audio Processor handles audio streams
7. Quality analysis is performed
8. Segments are concatenated
9. Final output is produced

## Configuration Management
- Configuration is hierarchical
- Each component has its own config section
- Validation occurs at component boundaries

## Error Handling
- Each component handles domain-specific errors
- Error recovery is managed at appropriate levels
- Cleanup ensures no orphaned files
