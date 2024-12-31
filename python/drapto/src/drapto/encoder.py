"""Video encoding module."""

import subprocess
from pathlib import Path
from typing import Optional, Dict, List

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
                self.fmt.print_check(f"Segment already encoded successfully: {segment.name}")
                continue
                
            segments.append((segment, output_segment))
            
        if not segments:
            self.fmt.print_error("No segments found to encode")
            return False
            
        # Create command list file
        cmd_list_file = segments_dir / "commands.txt"
        with open(cmd_list_file, 'w') as f:
            for input_segment, output_segment in segments:
                # Create the command with retries and fallbacks
                cmd = [
                    # First attempt with default settings
                    'ab-av1', 'auto-encode',
                    '--input', str(input_segment),
                    '--output', str(output_segment),
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
                
                # Print command in readable format
                self.fmt.print_check("ab-av1 command:")
                formatted_cmd = "    " + "\n    ".join([
                    "ab-av1",
                    "auto-encode",
                    *[f"{arg}" for arg in cmd[2:]]
                ])
                self.fmt.print_check(formatted_cmd)
                
                # Add crop filter if specified
                if crop_filter:
                    cmd.extend(['--vfilter', crop_filter])
                    
                # Add hardware acceleration if available
                if self.config.hw_accel_opts:
                    cmd.extend(['--hwaccel-args', self.config.hw_accel_opts])
                    
                # Write the command to the file, properly quoted
                f.write(' '.join(f"'{arg}'" if ' ' in str(arg) else str(arg) for arg in cmd))
                f.write(' || ')
                
                # Second attempt with more samples
                cmd = [
                    'ab-av1', 'auto-encode',
                    '--input', str(input_segment),
                    '--output', str(output_segment),
                    '--encoder', 'libsvtav1',
                    '--min-vmaf', str(self.config.target_vmaf),
                    '--preset', str(self.config.preset),
                    '--svt', self.config.svt_params,
                    '--keyint', '10s',
                    '--samples', '6',
                    '--sample-duration', '2s',
                    '--vmaf', 'n_subsample=8:pool=harmonic_mean',
                    '--quiet'
                ]
                
                if crop_filter:
                    cmd.extend(['--vfilter', crop_filter])
                    
                if self.config.hw_accel_opts:
                    cmd.extend(['--hwaccel-args', self.config.hw_accel_opts])
                    
                f.write(' '.join(f"'{arg}'" if ' ' in str(arg) else str(arg) for arg in cmd))
                f.write(' || ')
                
                # Final attempt with lower VMAF target
                cmd = [
                    'ab-av1', 'auto-encode',
                    '--input', str(input_segment),
                    '--output', str(output_segment),
                    '--encoder', 'libsvtav1',
                    '--min-vmaf', str(self.config.target_vmaf - 2),
                    '--preset', str(self.config.preset),
                    '--svt', self.config.svt_params,
                    '--keyint', '10s',
                    '--samples', '6',
                    '--sample-duration', '2s',
                    '--vmaf', 'n_subsample=8:pool=harmonic_mean',
                    '--quiet'
                ]
                
                if crop_filter:
                    cmd.extend(['--vfilter', crop_filter])
                    
                if self.config.hw_accel_opts:
                    cmd.extend(['--hwaccel-args', self.config.hw_accel_opts])
                    
                f.write(' '.join(f"'{arg}'" if ' ' in str(arg) else str(arg) for arg in cmd))
                f.write('\n')
        
        # Run parallel encoding with minimal output
        parallel_cmd = [
            'parallel',
            '--will-cite',
            '--noswap',
            '--halt', 'soon,fail=1',
            '--jobs', str(self.config.jobs),
            '--joblog', str(output_dir / 'parallel.log'),
            '--line-buffer',
            '--no-notice',
            '--no-progress',
            '--no-bar',
            '--quiet',
            'bash -c {}',
            ':::', str(cmd_list_file)
        ]
        
        # Print the command for debugging
        self.fmt.print_check("Running parallel command:")
        formatted_cmd = "    " + "\n    ".join([str(arg) for arg in parallel_cmd])
        self.fmt.print_check(formatted_cmd)
        
        # Create a progress tracker
        total_segments = len(segments)
        self.fmt.print_check(f"Processing {total_segments} segments in parallel...")
        
        # Run the command and process output
        completed_segments = 0
        process = subprocess.Popen(
            parallel_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
                
            if "Successfully encoded segment" in line:
                completed_segments += 1
                progress = (completed_segments / total_segments) * 100
                self.fmt.print_check(f"Progress: {progress:.1f}% ({completed_segments}/{total_segments} segments)")
                
            # Print important messages
            if "Running command" in line or "Encoded" in line:
                self.fmt.print_check(line.strip())
                
        # Get the return code
        return_code = process.wait()
        if return_code != 0:
            self.fmt.print_error(f"Error encoding segments: Process returned {return_code}")
            return False
            
        self.fmt.print_success("Parallel encoding completed")
        
        # Clean up
        if cmd_list_file.exists():
            cmd_list_file.unlink()
            
        return True
        
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
        
        # Print command in readable format
        self.fmt.print_check("ab-av1 command:")
        formatted_cmd = "    " + "\n    ".join([
            "ab-av1",
            "auto-encode",
            *[f"{arg}" for arg in cmd[2:]]
        ])
        self.fmt.print_check(formatted_cmd)
        
        # Add crop filter if specified
        if crop_filter:
            cmd.extend(['--vfilter', crop_filter])
            
        # Add hardware acceleration if available
        if self.config.hw_accel_opts:
            cmd.extend(['--hwaccel-args', self.config.hw_accel_opts])
            
        # Run encoding
        subprocess.run(cmd, check=True)
        return True
            
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
