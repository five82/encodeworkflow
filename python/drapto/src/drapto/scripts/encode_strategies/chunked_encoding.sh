#!/usr/bin/env bash

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Import utilities
source "${SCRIPT_DIR}/utils/formatting.sh"
source "${SCRIPT_DIR}/common/config.sh"
source "${SCRIPT_DIR}/common/state_management.sh"

###################
# Chunked Encoding Strategy
###################

# Initialize working directories
# Args:
#   $1: Output file path
initialize_working_dirs() {
    local output_file="$1"
    
    # Set up working directories as subdirectories of output location
    export WORKING_DIR="${output_file}_work"
    export SEGMENTS_DIR="${WORKING_DIR}/segments"
    export ENCODED_SEGMENTS_DIR="${WORKING_DIR}/encoded"
    export TEMP_DATA_DIR="${WORKING_DIR}/data"

    print_check "Setting up working directories..."

    # Clean up old directories if they exist
    if [[ -d "$WORKING_DIR" ]]; then
        print_check "Cleaning up old working directory..."
        rm -rf "$WORKING_DIR"
    fi

    # Create fresh directories
    for dir in "$WORKING_DIR" "$SEGMENTS_DIR" "$ENCODED_SEGMENTS_DIR" "$TEMP_DATA_DIR"; do
        mkdir -p "$dir" || {
            print_error "Failed to create directory: $dir"
            return 1
        }
    done

    # Initialize tracking files
    if ! initialize_tracking_files; then
        print_error "Failed to initialize tracking files"
        return 1
    fi

    print_success "Working directories initialized"
    return 0
}

# Initialize chunked encoding
# Args:
#   $1: Input file path
#   $2: Output file path
#   $3: Options string (optional)
initialize_encoding() {
    local input_file="$1"
    local output_file="$2"
    
    print_check "Initializing chunked encoding strategy..."
    
    # Initialize working directories
    if ! initialize_working_dirs "$output_file"; then
        print_error "Failed to initialize working directories"
        return 1
    fi

    # Create a temporary Python script to create the encoding job
    local tmp_script
    tmp_script=$(mktemp)
    cat > "$tmp_script" << 'EOF'
from drapto.scripts.common.encoding_state import EncodingState
import sys

temp_dir = sys.argv[1]
input_file = sys.argv[2]
output_file = sys.argv[3]

state = EncodingState(temp_dir)
job_id = state.create_job(input_file, output_file, "chunked")
print(job_id)
EOF
    
    # Run the Python script
    local job_id
    job_id=$(PYTHONPATH=/home/ken/projects/encodeworkflow/python/drapto/src python3 "$tmp_script" "${TEMP_DATA_DIR}" "${input_file}" "${output_file}")
    local status=$?

    # Clean up temporary script
    rm "$tmp_script"

    # Check if job creation was successful
    if [[ $status -ne 0 ]]; then
        print_error "Failed to create encoding job"
        return 1
    fi

    # Export job ID for other functions to use
    export JOB_ID="$job_id"
    print_check "Created encoding job: $job_id"

    return 0
}

# Prepare video by segmenting it
# Args:
#   $1: Input file path
#   $2: Output file path
#   $3: Options string (optional)
prepare_video() {
    local input_file="$1"
    local output_file="$2"
    
    echo "DEBUG: prepare_video called with: input='$input_file', output='$output_file'"
    print_check "Preparing video for chunked encoding..."
    
    # Segment the video
    if ! segment_video "$input_file" "$SEGMENTS_DIR"; then
        print_error "Failed to segment video"
        return 1
    fi
    
    return 0
}

# Encode video segments in parallel
# Args:
#   $1: Input file path
#   $2: Output file path
#   $3: Options string (optional)
encode_video() {
    local input_file="$1"
    local output_file="$2"
    local options="$3"
    
    print_check "Encoding video segments..."
    
    # Parse options
    local target_vmaf="$TARGET_VMAF"
    local disable_crop="$DISABLE_CROP"
    local crop_filter=""
    
    # Get crop filter if needed
    if [[ "$disable_crop" != "true" ]]; then
        crop_filter=$(detect_crop "$input_file" "$disable_crop")
    fi
    
    # Encode segments
    if ! encode_segments "$SEGMENTS_DIR" "$ENCODED_SEGMENTS_DIR" "$target_vmaf" "$disable_crop" "$crop_filter"; then
        print_error "Failed to encode segments"
        return 1
    fi
    
    return 0
}

# Finalize by concatenating segments
# Args:
#   $1: Input file path
#   $2: Output file path
#   $3: Options string (optional)
finalize_encoding() {
    local input_file="$1"
    local output_file="$2"
    
    print_check "Finalizing chunked encoding..."
    
    # Concatenate segments
    if ! concatenate_segments "$output_file"; then
        print_error "Failed to concatenate segments"
        return 1
    fi
    
    # Cleanup temporary files
    cleanup_temp_files
    
    return 0
}

# Check if this strategy can handle the input
# Args:
#   $1: Input file path
can_handle() {
    local input_file="$1"
    
    # Chunked encoding can handle any input that's not Dolby Vision
    if ! detect_dolby_vision "$input_file"; then
        return 0
    fi
    return 1
}

# Validate video segments
validate_segments() {
    print_check "Validating segments..."
    local dir="$1"
    local min_file_size=1024  # 1KB minimum file size

    local segment_count
    segment_count=$(find "$dir" -name "*.mkv" -type f | wc -l)
    [[ $segment_count -lt 1 ]] && print_error "No segments found in $dir"

    local invalid_segments=0
    while IFS= read -r -d $'\0' segment; do
        local file_size
        file_size=$(stat -f%z "$segment" 2>/dev/null || stat -c%s "$segment")
        
        if [[ $file_size -lt $min_file_size ]] || ! "${FFPROBE}" -v error "$segment" >/dev/null 2>&1; then
            print_warning "Invalid segment found: $segment"
            ((invalid_segments++))
        fi
    done < <(find "$dir" -name "*.mkv" -type f -print0)

    [[ $invalid_segments -gt 0 ]] && print_error "Found $invalid_segments invalid segments"
    print_success "Successfully validated $segment_count segments"
}

# Validate a single segment file
# Args:
#   $1: Segment file path
validate_single_segment() {
    local segment_file="$1"

    # Check if file exists and is readable
    if [[ ! -f "$segment_file" ]] || [[ ! -r "$segment_file" ]]; then
        print_error "Segment file does not exist or is not readable: $segment_file"
        return 1
    fi

    # Check if file is a valid video file using ffprobe
    if ! "$FFPROBE" -v error -select_streams v:0 -show_entries stream=codec_type -of csv=p=0 "$segment_file" > /dev/null 2>&1; then
        print_error "Invalid video file: $segment_file"
        return 1
    fi

    return 0
}

# Segment video into chunks
segment_video() {
    print_check "Segmenting video..."
    local input_file="$1"
    local output_dir="$2"

    mkdir -p "$output_dir"

    # Segment the video
    "${FFMPEG}" -hide_banner -loglevel error -i "$input_file" \
        -c:v copy \
        -an \
        -f segment \
        -segment_time "$SEGMENT_LENGTH" \
        -reset_timestamps 1 \
        "${output_dir}/%04d.mkv"

    # Add segments to job tracking
    local index=0
    for segment in "${output_dir}"/*.mkv; do
        if [[ -f "$segment" ]]; then
            # Validate segment before adding
            if ! validate_single_segment "$segment"; then
                print_error "Failed to validate segment: $segment"
                return 1
            fi
            
            if ! add_segment_to_tracking "$segment" "$index" "0.0" "$(get_segment_duration "$segment")"; then
                print_error "Failed to add segment to tracking: $segment"
                return 1
            fi
            ((index++))
        fi
    done

    validate_segments "$output_dir"
}

# Encode video segments using ab-av1
encode_segments() {
    local input_dir="$1"
    local output_dir="$2"
    local target_vmaf="$3"
    local disable_crop="$4"
    local crop_filter="$5"

    # Check if GNU Parallel is installed
    if ! check_parallel_installation; then
        print_error "Cannot proceed with parallel encoding without GNU Parallel"
        return 1
    fi

    # Create output directory if it doesn't exist
    mkdir -p "$output_dir"

    # Create a temporary file to store segment encoding commands
    local cmd_file=$(mktemp)
    
    # Build the command list
    local segment_count=0
    for segment in "$input_dir"/*.mkv; do
        if [[ -f "$segment" ]]; then
            local segment_name=$(basename "$segment")
            local output_segment="${output_dir}/${segment_name}"
            
            # Skip if output segment already exists and has non-zero size
            if [[ -f "$output_segment" ]] && [[ -s "$output_segment" ]]; then
                print_check "Segment already encoded successfully: ${segment_name}"
                continue
            fi

            # Only pass crop filter if it's not empty
            local vfilter_args=""
            if [[ -n "$crop_filter" ]]; then
                vfilter_args="--vfilter $crop_filter"
            fi

            # Build the encoding command
            echo "encode_single_segment '$segment' '$output_segment' '$target_vmaf' '$vfilter_args'" >> "$cmd_file"
            ((segment_count++))
        fi
    done

    if [[ $segment_count -eq 0 ]]; then
        print_error "No segments found to encode in $input_dir"
        rm "$cmd_file"
        return 1
    fi

    # Define the single segment encoding function
    encode_single_segment() {
        local segment="$1"
        local output_segment="$2"
        local target_vmaf="$3"
        local vfilter_args="$4"
        local segment_index=$(get_segment_index "$segment")
        
        # Get encoding status and attempts
        local encoding_data
        encoding_data=$(python3 -c "import json
with open('${TEMP_DATA_DIR}/encoding.json', 'r') as f:
    data = json.load(f)
segment = data['segments'].get('${segment_index}', {})
print(f'{segment.get(\"attempts\", 0)}\n{segment.get(\"last_strategy\", \"\")}')
")
        local attempts=$(echo "$encoding_data" | head -n1)
        local last_strategy=$(echo "$encoding_data" | tail -n1)
        
        # Check if we've exceeded max attempts
        if [[ $attempts -ge 3 ]]; then
            update_segment_encoding_status "$segment_index" "failed" "Exceeded maximum retry attempts" "max_exceeded"
            print_error "Failed to encode segment after $attempts attempts: $(basename "$segment")"
            return 1
        fi
        
        # Try default strategy first
        if [[ $attempts -eq 0 ]] || [[ $last_strategy != "default" ]]; then
            update_segment_encoding_status "$segment_index" "encoding" "" "default"
            if ab-av1 auto-encode \
                --input "$segment" \
                --output "$output_segment" \
                --encoder libsvtav1 \
                --min-vmaf "$target_vmaf" \
                --preset "$PRESET" \
                --svt "tune=0:film-grain=0:film-grain-denoise=0" \
                --keyint 10s \
                --samples "$VMAF_SAMPLE_COUNT" \
                --sample-duration "${VMAF_SAMPLE_LENGTH}s" \
                --vmaf "n_subsample=8:pool=harmonic_mean" \
                $vfilter_args \
                --quiet; then
                update_segment_encoding_status "$segment_index" "completed" "" "default"
                return 0
            fi
        fi
        
        # Try more samples strategy
        if [[ $attempts -lt 2 ]] || [[ $last_strategy != "more_samples" ]]; then
            update_segment_encoding_status "$segment_index" "encoding" "" "more_samples"
            if ab-av1 auto-encode \
                --input "$segment" \
                --output "$output_segment" \
                --encoder libsvtav1 \
                --min-vmaf "$target_vmaf" \
                --preset "$PRESET" \
                --svt "tune=0:film-grain=0:film-grain-denoise=0" \
                --keyint 10s \
                --samples 6 \
                --sample-duration "2s" \
                --vmaf "n_subsample=8:pool=harmonic_mean" \
                $vfilter_args \
                --quiet; then
                update_segment_encoding_status "$segment_index" "completed" "" "more_samples"
                return 0
            fi
        fi
        
        # Try lower VMAF target strategy
        if [[ $attempts -lt 3 ]] || [[ $last_strategy != "lower_vmaf" ]]; then
            local lower_vmaf=$((target_vmaf - 2))
            update_segment_encoding_status "$segment_index" "encoding" "" "lower_vmaf"
            if ab-av1 auto-encode \
                --input "$segment" \
                --output "$output_segment" \
                --encoder libsvtav1 \
                --min-vmaf "$lower_vmaf" \
                --preset "$PRESET" \
                --svt "tune=0:film-grain=0:film-grain-denoise=0" \
                --keyint 10s \
                --samples 6 \
                --sample-duration "2s" \
                --vmaf "n_subsample=8:pool=harmonic_mean" \
                $vfilter_args \
                --quiet; then
                update_segment_encoding_status "$segment_index" "completed" "" "lower_vmaf"
                return 0
            fi
        fi
        
        update_segment_encoding_status "$segment_index" "failed" "Failed to encode segment after all strategies" "all_failed"
        print_error "Failed to encode segment after all strategies: $(basename "$segment")"
        return 1
    }
    # Export all required functions for parallel environment
    export -f encode_single_segment
    export -f print_check
    export -f print_error
    export -f print_success
    export -f print_warning
    export -f get_segment_index
    export -f get_segment_duration
    export -f update_segment_encoding_status
    export -f update_tracking_timestamps
    
    # Export required variables
    export PRESET
    export VMAF_SAMPLE_COUNT
    export VMAF_SAMPLE_LENGTH
    export FFMPEG
    export FFPROBE
    export TEMP_DATA_DIR
    export ENCODED_SEGMENTS_DIR

    # Use GNU Parallel to process segments
    # --jobs determines how many parallel jobs to run (0 means number of CPU cores)
    # --halt soon,fail=1 stops all jobs if any job fails
    # --no-notice suppresses citation notice
    # --line-buffer ensures output lines are not mixed
    if ! parallel --no-notice --line-buffer --halt soon,fail=1 --jobs 0 :::: "$cmd_file"; then
        rm "$cmd_file"
        return 1
    fi

    rm "$cmd_file"
    return 0
}

# Concatenate encoded segments back into a single file
concatenate_segments() {
    local output_file="$1"
    local concat_file="${WORKING_DIR}/concat.txt"

    # Ensure directories exist
    mkdir -p "${WORKING_DIR}" "${ENCODED_SEGMENTS_DIR}"

    # Create concat file with proper format
    > "$concat_file"
    
    # Check if there are any mkv files
    if ! compgen -G "${ENCODED_SEGMENTS_DIR}/*.mkv" > /dev/null; then
        print_error "No .mkv files found in ${ENCODED_SEGMENTS_DIR}"
        return 1
    fi

    # Add each segment to the concat file
    for segment in "${ENCODED_SEGMENTS_DIR}"/*.mkv; do
        if [[ -f "$segment" ]]; then
            echo "file '$(realpath "$segment")'" >> "$concat_file"
        fi
    done

    if [[ ! -s "$concat_file" ]]; then
        print_error "No segments found to concatenate"
        return 1
    fi

    # Concatenate video segments directly to output file
    if ! "$FFMPEG" -hide_banner -loglevel error -f concat -safe 0 -i "$concat_file" -c copy "$output_file"; then
        print_error "Failed to concatenate video segments"
        return 1
    fi

    return 0
}

# Cleanup after an error occurs
# Args:
#   $1: Job ID
#   $2: Output directory
#   $3: Error message (optional)
cleanup_on_error() {
    local job_id="$1"
    local output_dir="$2"
    local error_msg="${3:-Encoding failed}"

    print_check "Starting cleanup after error: $error_msg"

    # Update job status to failed
    update_job_status "$job_id" "failed" "$error_msg"

    # Only attempt cleanup if output directory exists
    if [[ -d "$output_dir" ]]; then
        # Clean up all subdirectories
        for subdir in "segments" "encoded" "data"; do
            if [[ -d "${output_dir}/${subdir}" ]]; then
                rm -rf "${output_dir}/${subdir}"
            fi
        done

        # Try to remove the working directory itself
        rmdir "$output_dir" 2>/dev/null || {
            print_warning "Could not remove working directory - it may contain other files"
        }
    fi

    print_success "Cleanup completed"
}

# Test directory initialization
# Args:
#   None
test_initialize_working_dirs() {
    print_check "Testing working directory initialization..."
    
    # Create a test output file path
    local test_output="/tmp/test_encode_output.mkv"
    
    # First initialization should succeed
    if ! initialize_working_dirs "$test_output"; then
        print_error "First initialization failed"
        return 1
    fi

    # Verify all directories exist
    local all_dirs_exist=true
    for dir in "$WORKING_DIR" "$SEGMENTS_DIR" "$ENCODED_SEGMENTS_DIR" "$TEMP_DATA_DIR"; do
        if [[ ! -d "$dir" ]]; then
            print_error "Directory not created: $dir"
            all_dirs_exist=false
        fi
    done

    if [[ "$all_dirs_exist" != "true" ]]; then
        return 1
    fi

    # Create a test file in working directory
    local test_file="${WORKING_DIR}/test_file.txt"
    echo "test" > "$test_file"

    # Second initialization should succeed and clean up old files
    if ! initialize_working_dirs "$test_output"; then
        print_error "Second initialization failed"
        return 1
    fi

    # Verify test file was cleaned up
    if [[ -f "$test_file" ]]; then
        print_error "Old files not cleaned up"
        return 1
    fi

    # Verify all directories exist again
    all_dirs_exist=true
    for dir in "$WORKING_DIR" "$SEGMENTS_DIR" "$ENCODED_SEGMENTS_DIR" "$TEMP_DATA_DIR"; do
        if [[ ! -d "$dir" ]]; then
            print_error "Directory not recreated: $dir"
            all_dirs_exist=false
        fi
    done

    if [[ "$all_dirs_exist" != "true" ]]; then
        return 1
    fi

    # Clean up test directories
    rm -rf "$WORKING_DIR"

    print_success "Directory initialization tests passed"
    return 0
}

# Initialize tracking files
# Args:
#   None
initialize_tracking_files() {
    print_check "Initializing tracking files..."

    # Create initial segments.json
    cat > "${TEMP_DATA_DIR}/segments.json" << 'EOF'
{
    "segments": [],
    "created_at": "",
    "updated_at": "",
    "total_segments": 0,
    "total_duration": 0.0
}
EOF

    # Create initial encoding.json
    cat > "${TEMP_DATA_DIR}/encoding.json" << 'EOF'
{
    "segments": {},
    "created_at": "",
    "updated_at": "",
    "total_attempts": 0,
    "failed_segments": 0,
    "max_attempts": 3,
    "retry_strategies": [
        {
            "name": "default",
            "description": "Default encoding settings",
            "samples": 4,
            "sample_duration": 1
        },
        {
            "name": "more_samples",
            "description": "More samples for better quality estimation",
            "samples": 6,
            "sample_duration": 2
        },
        {
            "name": "lower_vmaf",
            "description": "Lower VMAF target by 2 points",
            "samples": 6,
            "sample_duration": 2,
            "vmaf_reduction": 2
        }
    ]
}
EOF

    # Create initial progress.json
    cat > "${TEMP_DATA_DIR}/progress.json" << 'EOF'
{
    "status": "initializing",
    "created_at": "",
    "updated_at": "",
    "total_progress": 0.0,
    "segments_completed": 0,
    "segments_failed": 0,
    "current_segment": null
}
EOF

    # Update timestamps
    update_tracking_timestamps

    print_success "Tracking files initialized"
    return 0
}

# Update timestamps in tracking files
# Args:
#   None
update_tracking_timestamps() {
    local current_time
    current_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Update segments.json timestamps
    PYTHONPATH="/home/ken/projects/encodeworkflow/python/drapto/src" python3 -c "
import json, sys
from datetime import datetime

def update_timestamps(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    if not data.get('created_at'):
        data['created_at'] = '${current_time}'
    data['updated_at'] = '${current_time}'
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

for file in ['segments.json', 'encoding.json', 'progress.json']:
    update_timestamps('${TEMP_DATA_DIR}/' + file)
"
}

# Add segment to tracking
# Args:
#   $1: Segment file path
#   $2: Segment index
#   $3: Start time
#   $4: Duration
add_segment_to_tracking() {
    local segment_path="$1"
    local index="$2"
    local start_time="$3"
    local duration="$4"
    
    # Get segment size
    local size
    size=$(stat -f%z "$segment_path" 2>/dev/null || stat -c%s "$segment_path")
    
    # Add segment to segments.json
    PYTHONPATH="/home/ken/projects/encodeworkflow/python/drapto/src" python3 -c "
import json, os
from datetime import datetime

# Update segments.json
with open('${TEMP_DATA_DIR}/segments.json', 'r') as f:
    data = json.load(f)

segment = {
    'index': ${index},
    'path': '${segment_path}',
    'size': ${size},
    'start_time': ${start_time},
    'duration': ${duration},
    'created_at': '$(date -u +"%Y-%m-%dT%H:%M:%SZ")'
}

data['segments'].append(segment)
data['total_segments'] = len(data['segments'])
data['total_duration'] += ${duration}

with open('${TEMP_DATA_DIR}/segments.json', 'w') as f:
    json.dump(data, f, indent=4)

# Initialize segment in encoding.json
with open('${TEMP_DATA_DIR}/encoding.json', 'r') as f:
    encoding_data = json.load(f)

encoding_data['segments'][str(${index})] = {
    'status': 'pending',
    'attempts': 0,
    'last_attempt': None,
    'error': None
}

with open('${TEMP_DATA_DIR}/encoding.json', 'w') as f:
    json.dump(encoding_data, f, indent=4)
"
    
    # Update timestamps
    update_tracking_timestamps
}

# Update segment encoding status
# Args:
#   $1: Segment index
#   $2: Status (pending, encoding, completed, failed)
#   $3: Error message (optional)
update_segment_encoding_status() {
    local index="$1"
    local status="$2"
    local error="${3:-}"
    local strategy="${4:-}"
    
    PYTHONPATH="/home/ken/projects/encodeworkflow/python/drapto/src" python3 -c "
import json
from datetime import datetime

# Update encoding.json
with open('${TEMP_DATA_DIR}/encoding.json', 'r') as f:
    data = json.load(f)

segment = data['segments'].get(str(${index}))
if not segment:
    segment = {
        'status': '${status}',
        'attempts': 0,
        'strategies_tried': [],
        'last_strategy': None,
        'error': None
    }
    data['segments'][str(${index})] = segment

segment['status'] = '${status}'
if '${strategy}':
    if 'strategies_tried' not in segment:
        segment['strategies_tried'] = []
    if '${strategy}' not in segment['strategies_tried']:
        segment['strategies_tried'].append('${strategy}')
        segment['attempts'] = len(segment['strategies_tried'])
    segment['last_strategy'] = '${strategy}'

if '${error}':
    segment['error'] = '${error}'
else:
    segment['error'] = None

data['total_attempts'] += 1
if '${status}' == 'failed':
    data['failed_segments'] += 1

with open('${TEMP_DATA_DIR}/encoding.json', 'w') as f:
    json.dump(data, f, indent=4)

# Update progress.json
with open('${TEMP_DATA_DIR}/progress.json', 'r') as f:
    progress = json.load(f)

progress['current_segment'] = int('${index}')
if '${status}' == 'completed':
    progress['segments_completed'] += 1
elif '${status}' == 'failed':
    progress['segments_failed'] += 1

with open('${TEMP_DATA_DIR}/progress.json', 'w') as f:
    json.dump(progress, f, indent=4)
"
    
    # Update timestamps
    update_tracking_timestamps
}

# Update overall encoding progress
# Args:
#   $1: Status
#   $2: Progress percentage (0-100)
update_encoding_progress() {
    local status="$1"
    local progress="$2"
    
    PYTHONPATH="/home/ken/projects/encodeworkflow/python/drapto/src" python3 -c "
import json

with open('${TEMP_DATA_DIR}/progress.json', 'r') as f:
    data = json.load(f)

data['status'] = '${status}'
data['total_progress'] = float(${progress})

with open('${TEMP_DATA_DIR}/progress.json', 'w') as f:
    json.dump(data, f, indent=4)
"
    
    # Update timestamps
    update_tracking_timestamps
}

# Get segment duration using ffprobe
# Args:
#   $1: Segment file path
get_segment_duration() {
    local segment_file="$1"
    local duration
    
    duration=$("${FFPROBE}" -v error -select_streams v:0 -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$segment_file")
    
    # Return duration or 0 if not found
    echo "${duration:-0.0}"
}

# Get segment index from filename
# Args:
#   $1: Segment file path
get_segment_index() {
    local segment_file="$1"
    local basename
    
    basename=$(basename "$segment_file")
    # Extract number from filename (e.g. 0001.mkv -> 1)
    base=${basename%.*}  # Remove extension
    
    # Check if the filename is all digits (after removing extension)
    if [[ "$base" =~ ^[0-9]+$ ]]; then
        # Convert to number (strips leading zeros)
        echo "$((10#$base))"
    else
        print_error "Invalid segment filename: $segment_file"
        echo "0"
    fi
}

# Test tracking file functions
# Args:
#   None
test_tracking_files() {
    print_check "Testing tracking file functions..."
    
    # Set up test environment
    local test_output="/tmp/test_encode_output.mkv"
    if ! initialize_working_dirs "$test_output"; then
        print_error "Failed to set up test environment"
        return 1
    fi

    # Initialize tracking files
    initialize_tracking_files

    # Test tracking file initialization
    for file in "segments.json" "encoding.json" "progress.json"; do
        if [[ ! -f "${TEMP_DATA_DIR}/${file}" ]]; then
            print_error "Tracking file not created: ${file}"
            return 1
        fi
    done

    # Test segment tracking
    local test_segment="${SEGMENTS_DIR}/0001.mkv"
    touch "$test_segment"
    
    if ! add_segment_to_tracking "$test_segment" "1" "0.0" "10.0"; then
        print_error "Failed to add segment to tracking"
        return 1
    fi

    # Verify segment was added to segments.json
    if ! grep -q "0001.mkv" "${TEMP_DATA_DIR}/segments.json"; then
        print_error "Segment not found in segments.json"
        return 1
    fi

    # Test retry functionality
    # First attempt - default strategy
    update_segment_encoding_status "1" "encoding" "" "default"
    update_segment_encoding_status "1" "failed" "First attempt failed" "default"

    # Second attempt - more samples strategy
    update_segment_encoding_status "1" "encoding" "" "more_samples"
    update_segment_encoding_status "1" "failed" "Second attempt failed" "more_samples"

    # Third attempt - lower vmaf strategy
    update_segment_encoding_status "1" "encoding" "" "lower_vmaf"
    update_segment_encoding_status "1" "completed" "" "lower_vmaf"

    # Verify retry tracking
    PYTHONPATH="/home/ken/projects/encodeworkflow/python/drapto/src" python3 -c "
import json
with open('${TEMP_DATA_DIR}/encoding.json', 'r') as f:
    data = json.load(f)

segment = data['segments']['1']
if 'default' not in segment['strategies_tried']:
    print('Default strategy not tracked')
    exit(1)
if 'more_samples' not in segment['strategies_tried']:
    print('More samples strategy not tracked')
    exit(1)
if 'lower_vmaf' not in segment['strategies_tried']:
    print('Lower VMAF strategy not tracked')
    exit(1)
if segment['attempts'] != 3:
    print('Attempts count incorrect')
    exit(1)
"

    # Check final status
    PYTHONPATH="/home/ken/projects/encodeworkflow/python/drapto/src" python3 -c "
import json
with open('${TEMP_DATA_DIR}/encoding.json', 'r') as f:
    data = json.load(f)

segment = data['segments']['1']
if segment['status'] != 'completed':
    print('Final status not updated')
    exit(1)
"

    # Test progress updates
    if ! update_encoding_progress "completed" "100.0"; then
        print_error "Failed to update progress"
        return 1
    fi

    # Verify progress was updated
    if ! grep -q "100.0" "${TEMP_DATA_DIR}/progress.json"; then
        print_error "Progress not updated in progress.json"
        return 1
    fi

    # Test max attempts
    local test_segment2="${SEGMENTS_DIR}/0002.mkv"
    touch "$test_segment2"
    add_segment_to_tracking "$test_segment2" "2" "0.0" "10.0"

    # Try all strategies and verify max attempts
    update_segment_encoding_status "2" "encoding" "" "default"
    update_segment_encoding_status "2" "failed" "First attempt failed" "default"
    update_segment_encoding_status "2" "encoding" "" "more_samples"
    update_segment_encoding_status "2" "failed" "Second attempt failed" "more_samples"
    update_segment_encoding_status "2" "encoding" "" "lower_vmaf"
    update_segment_encoding_status "2" "failed" "Third attempt failed" "lower_vmaf"

    # Try one more attempt - should be rejected
    update_segment_encoding_status "2" "encoding" "" "default"

    # Verify max attempts enforced
    tracking_data=$(cat "${TEMP_DATA_DIR}/encoding.json")
    if ! echo "$tracking_data" | grep -q '"status": "failed"' && \
       ! echo "$tracking_data" | grep -q '"attempts": 3'; then
        print_error "Max attempts not enforced"
        return 1
    fi

    # Clean up
    rm -f "$test_segment" "$test_segment2"
    rm -rf "$WORKING_DIR"

    print_success "Tracking file tests passed"
    return 0
}

# Run tests if TEST_MODE is enabled
if [[ "${TEST_MODE:-false}" == "true" ]]; then
    if ! test_initialize_working_dirs; then
        print_error "Directory initialization tests failed"
        exit 1
    fi
    
    if ! test_tracking_files; then
        print_error "Tracking file tests failed"
        exit 1
    fi
fi
