"""Minimal wrapper for bash encoding scripts."""
import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Union, List

def debug_print(msg: str) -> None:
    """Print debug message with timestamp."""
    timestamp = time.strftime("%H:%M:%S", time.gmtime())
    sys.stderr.write(f"[DEBUG {timestamp}] {msg}\n")
    sys.stderr.flush()

class Encoder:
    """Minimal wrapper for bash encoding scripts."""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent / "scripts"
        
        # Ensure script directory exists
        if not self.script_dir.exists():
            raise RuntimeError(f"Script directory not found: {self.script_dir}")
            
        # Main encode script
        self.encode_script = self.script_dir / "encode.sh"
        if not self.encode_script.exists():
            raise RuntimeError(f"Encode script not found: {self.encode_script}")
        
        # Make scripts executable
        for script in self.script_dir.glob("*.sh"):
            script.chmod(0o755)
    
    def encode(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> None:
        """Encode video file(s).
        
        Args:
            input_path: Input file or directory
            output_path: Output file or directory
        """
        debug_print("Starting encode function")
        input_path = Path(input_path).resolve()
        output_path = Path(output_path).resolve()
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input not found: {input_path}")
            
        # Set up environment
        env = os.environ.copy()
        env["SCRIPT_DIR"] = str(self.script_dir)
        env["PYTHONUNBUFFERED"] = "1"
        env["STDBUF_ONOPTION"] = "L"
        
        debug_print(f"Environment variables set: PYTHONUNBUFFERED={env.get('PYTHONUNBUFFERED')}, STDBUF_ONOPTION={env.get('STDBUF_ONOPTION')}")
        
        # Create temp directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            env["TEMP_DIR"] = str(temp_path)
            debug_print(f"Created temp directory: {temp_path}")
            
            # Handle directory vs file
            if input_path.is_dir():
                if not output_path.is_dir():
                    output_path.mkdir(parents=True, exist_ok=True)
                    
                # Use actual paths
                env["INPUT_DIR"] = str(input_path)
                env["OUTPUT_DIR"] = str(output_path)
                env["LOG_DIR"] = str(temp_path / "logs")
                debug_print("Processing directory input")
                
            else:
                if output_path.is_dir():
                    output_path = output_path / input_path.name
                    
                # Use parent directories
                env["INPUT_DIR"] = str(input_path.parent)
                env["OUTPUT_DIR"] = str(output_path.parent)
                env["LOG_DIR"] = str(temp_path / "logs")
                env["INPUT_FILE"] = input_path.name
                debug_print("Processing single file input")
            
            debug_print(f"Input path: {input_path}")
            debug_print(f"Output path: {output_path}")
            
            # Run encode script with real-time output
            try:
                debug_print("Starting subprocess")
                cmd = ["stdbuf", "-oL", "-eL", str(self.encode_script)]
                debug_print(f"Command: {' '.join(cmd)}")
                
                process = subprocess.Popen(
                    cmd,
                    cwd=str(self.script_dir),
                    env=env,
                    stdout=sys.stdout.fileno(),
                    stderr=sys.stderr.fileno(),
                    bufsize=0,  # Unbuffered
                    text=True
                )
                
                # Wait for process to complete
                process.wait()
                debug_print(f"Process finished with return code {process.returncode}")
                
                # Check return code
                if process.returncode != 0:
                    raise RuntimeError(f"Encoding failed with return code {process.returncode}")
                    
            except Exception as e:
                debug_print(f"Exception occurred: {str(e)}")
                raise RuntimeError(f"Encoding failed: {str(e)}")
            
            debug_print("Encode function completed successfully")
