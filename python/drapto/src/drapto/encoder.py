"""Video encoding module."""

import subprocess
from pathlib import Path
from typing import Optional, Dict, List
import os
import tempfile

from loguru import logger

from .formatting import TerminalFormatter


class VideoEncoder:
    """Video encoder class."""
    
    def __init__(self, config: 'EncodingConfig'):
        """Initialize encoder.
        
        Args:
            config: Encoding configuration
        """
        self.config = config
        self.fmt = TerminalFormatter()
        
    def encode_segments_parallel(
        self,
        segments_dir: Path,
        output_dir: Path,
        crop_filter: Optional[str] = None
    ) -> bool:
        """Encode video segments in parallel using ab-av1.
        
        Args:
            segments_dir: Directory containing input segments
            output_dir: Directory for output segments
            crop_filter: Optional crop filter
            
        Returns:
            True if encoding was successful
        """
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get list of segments to encode
        segments = []
        for segment in sorted(segments_dir.glob('*.mkv')):
            output_segment = output_dir / segment.name
            
            # Skip if already encoded successfully
            if output_segment.exists() and output_segment.stat().st_size > 0:
                self.fmt.print_check(f"\u2713 Segment already encoded: {segment.name}")
                continue
                
            segments.append(segment)
            
        if not segments:
            self.fmt.print_error("No segments found to encode")
            return False
            
        # Encode segments in parallel
        return self._encode_segments_parallel(segments, output_dir)
            
    def _encode_segments_parallel(self, segments: List[Path], output_dir: Path) -> bool:
        """Encode segments in parallel using GNU parallel."""
        # Create a temporary script file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            script_path = f.name
            # Write the function definition
            f.write("""
encode_single_segment() {
    input_file="$1"
    output_file="$(dirname "$1")/../encoded/$(basename "$1")"
    export RUST_LOG=ab_av1=error

    ab-av1 auto-encode \\
        --input "$input_file" \\
        --output "$output_file" \\
        --encoder libsvtav1 \\
        --min-vmaf {} \\
        --preset {} \\
        --svt {} \\
        --keyint 10s \\
        --samples {} \\
        --sample-duration {}s \\
        --vmaf n_subsample=8:pool=harmonic_mean \\
        --quiet
}
export -f encode_single_segment
""".format(
                self.config.target_vmaf,
                self.config.preset,
                self.config.svt_params,
                self.config.vmaf_sample_count,
                self.config.vmaf_sample_length
            ))

        # Create the output directory
        output_dir.mkdir(exist_ok=True)

        # Build parallel command
        cmd = [
            'parallel',
            '--jobs', str(self.config.parallel_jobs),
            '--line-buffer',  # Line buffer output
            '--no-notice',    # Remove parallel notice
            '--quiet',        # Reduce parallel's own output
            '--will-cite',    # Suppress citation notice
            'source {} && encode_single_segment'.format(script_path),
            ':::',
            *[str(s) for s in segments]
        ]

        # Run encoding
        try:
            env = os.environ.copy()
            env['RUST_LOG'] = 'ab_av1=error'
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                text=True
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line.strip():
                    print(line, end='', flush=True)
                
            return process.returncode == 0
        except subprocess.CalledProcessError as e:
            self.fmt.print_error(f"Failed to encode segments in parallel: {e}")
            return False
        finally:
            # Clean up the temporary script
            os.unlink(script_path)
        
    def encode_segment(
        self,
        input_file: Path,
        output_file: Path,
        crop_filter: Optional[str] = None
    ) -> bool:
        """Encode a single video segment.
        
        Args:
            input_file: Input video file
            output_file: Output video file
            crop_filter: Optional crop filter
            
        Returns:
            True if encoding was successful
        """
        return self._encode_with_params(
            input_file,
            output_file,
            crop_filter=crop_filter,
            target_vmaf=self.config.target_vmaf,
            samples=self.config.vmaf_sample_count,
            sample_duration=self.config.vmaf_sample_length
        )
            
    def _encode_with_params(
        self,
        input_file: Path,
        output_file: Path,
        crop_filter: Optional[str] = None,
        target_vmaf: Optional[float] = None,
        samples: Optional[int] = None,
        sample_duration: Optional[int] = None
    ) -> bool:
        """Encode with specific parameters.
        
        Args:
            input_file: Input video file
            output_file: Output video file
            crop_filter: Optional crop filter
            target_vmaf: Optional target VMAF score
            samples: Optional number of VMAF samples
            sample_duration: Optional VMAF sample duration
            
        Returns:
            True if encoding was successful
        """
        # Build command
        cmd = [
            'ab-av1', 'auto-encode',
            '--input', str(input_file),
            '--output', str(output_file),
            '--encoder', 'libsvtav1',
            '--min-vmaf', str(target_vmaf or self.config.target_vmaf),
            '--preset', str(self.config.preset),
            '--svt', self.config.svt_params,
            '--keyint', '10s',
            '--samples', str(samples or self.config.vmaf_sample_count),
            '--sample-duration', f"{sample_duration or self.config.vmaf_sample_length}s",
            '--vmaf', 'n_subsample=8:pool=harmonic_mean',
            '--quiet'
        ]
        
        # Add crop filter if specified
        if crop_filter:
            cmd.extend(['--vfilter', crop_filter])
            
        # Add hardware acceleration if available
        if self.config.hw_accel_opts:
            cmd.extend(['--hwaccel-args', self.config.hw_accel_opts])
            
        # Set up environment with RUST_LOG=error
        env = os.environ.copy()
        env['RUST_LOG'] = 'ab_av1=error'
        
        # Run encoding
        try:
            self.fmt.print_check(f"Running command: {' '.join(str(x) for x in cmd)}")
            subprocess.run(cmd, check=True, env=env)
            return True
        except subprocess.CalledProcessError as e:
            self.fmt.print_error(f"Failed to encode segment: {e}")
            return False
            
    def _get_ab_av1_command(
        self,
        crop_filter: Optional[str],
        input_pattern: Path,
        output_pattern: Path
    ) -> str:
        """Get ab-av1 command for parallel encoding.
        
        Args:
            crop_filter: Optional crop filter
            input_pattern: Input file pattern
            output_pattern: Output file pattern
            
        Returns:
            ab-av1 command string
        """
        cmd = [
            'env', 'RUST_LOG=ab_av1=error',  # Set environment variable for ab-av1
            'ab-av1', 'auto-encode',
            '--input', str(input_pattern),
            '--output', str(output_pattern),
            '--encoder', 'libsvtav1',
            '--min-vmaf', str(self.config.target_vmaf),
            '--preset', str(self.config.preset),
            '--svt', self.config.svt_params,
            '--keyint', '10s',
            '--samples', str(self.config.vmaf_sample_count),
            '--sample-duration', f"{self.config.vmaf_sample_length}s",
            '--vmaf', 'n_subsample=8:pool=harmonic_mean',
            '--quiet'
        ]
        
        # Add crop filter if specified
        if crop_filter:
            cmd.extend(['--vfilter', crop_filter])
            
        # Add hardware acceleration if available
        if self.config.hw_accel_opts:
            cmd.extend(['--hwaccel-args', self.config.hw_accel_opts])
            
        return ' '.join(cmd)
