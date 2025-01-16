#!/usr/bin/env bash

###################
# State Management
###################

# Import common utilities
source "${SCRIPT_DIR}/utils/formatting.sh"

# Create a new encoding job
# Args:
#   $1: Input file path
#   $2: Output file path
#   $3: Strategy name
create_encoding_job() {
    local input_file="$1"
    local output_file="$2"
    local strategy="$3"
    
    python3 -c "
from drapto.scripts.common.encoding_state import EncodingState
state = EncodingState('${TEMP_DATA_DIR}')
job_id = state.create_job('${input_file}', '${output_file}', '${strategy}')
print(job_id)
"
}

# Update job status
# Args:
#   $1: Job ID
#   $2: Status (pending, initializing, preparing, encoding, finalizing, completed, failed)
#   $3: Error message (optional)
update_job_status() {
    local job_id="$1"
    local status="$2"
    local error_msg="$3"
    
    if [[ -n "$error_msg" ]]; then
        python3 -c "
from drapto.scripts.common.encoding_state import EncodingState, JobStatus
state = EncodingState('${TEMP_DATA_DIR}')
state.update_job_status('${job_id}', JobStatus('${status}'), '${error_msg}')
"
    else
        python3 -c "
from drapto.scripts.common.encoding_state import EncodingState, JobStatus
state = EncodingState('${TEMP_DATA_DIR}')
state.update_job_status('${job_id}', JobStatus('${status}'))
"
    fi
}

# Update job statistics
# Args:
#   $1: Job ID
#   $2: Input size (bytes)
#   $3: Output size (bytes)
#   $4: VMAF score
update_job_stats() {
    local job_id="$1"
    local input_size="$2"
    local output_size="$3"
    local vmaf_score="$4"
    
    python3 -c "
from drapto.scripts.common.encoding_state import EncodingState
state = EncodingState('${TEMP_DATA_DIR}')
state.update_job_stats(
    '${job_id}',
    input_size=${input_size},
    output_size=${output_size},
    vmaf_score=${vmaf_score}
)
"
}

# Get job information
# Args:
#   $1: Job ID
get_job_info() {
    local job_id="$1"
    
    python3 -c "
from drapto.scripts.common.encoding_state import EncodingState
import json
state = EncodingState('${TEMP_DATA_DIR}')
job = state.get_job('${job_id}')
print(json.dumps(job.__dict__, default=str))
"
}

# Get all jobs information
get_all_jobs() {
    python3 -c "
from drapto.scripts.common.encoding_state import EncodingState
import json
state = EncodingState('${TEMP_DATA_DIR}')
jobs = state.get_all_jobs()
print(json.dumps([job.__dict__ for job in jobs], default=str))
"
}
