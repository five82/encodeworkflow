"""Terminal formatting module."""

import os
import sys
from typing import Optional


class TerminalFormatter:
    """Terminal formatting class."""
    
    def __init__(self):
        """Initialize terminal formatter."""
        self.has_color = self._check_color_support()
        
        # Basic formatting
        self.bold = "\033[1m" if self.has_color else ""
        self.reset = "\033[0m" if self.has_color else ""
        
        # Basic colors
        self.green = "\033[32m" if self.has_color else ""
        self.yellow = "\033[33m" if self.has_color else ""
        self.blue = "\033[34m" if self.has_color else ""
        self.magenta = "\033[35m" if self.has_color else ""
        self.cyan = "\033[36m" if self.has_color else ""
        self.white = "\033[37m" if self.has_color else ""
        self.red = "\033[31m" if self.has_color else ""
        
        # Bold + color combinations
        self.bold_green = f"{self.bold}{self.green}" if self.has_color else ""
        self.bold_yellow = f"{self.bold}{self.yellow}" if self.has_color else ""
        self.bold_blue = f"{self.bold}{self.blue}" if self.has_color else ""
        self.bold_magenta = f"{self.bold}{self.magenta}" if self.has_color else ""
        self.bold_cyan = f"{self.bold}{self.cyan}" if self.has_color else ""
        self.bold_white = f"{self.bold}{self.white}" if self.has_color else ""
        self.bold_red = f"{self.bold}{self.red}" if self.has_color else ""
        
    def _check_color_support(self) -> bool:
        """Check if terminal supports colors.
        
        Returns:
            True if terminal supports colors
        """
        # Check if output is a terminal
        if not sys.stdout.isatty():
            return False
            
        # Check for NO_COLOR environment variable
        if os.environ.get("NO_COLOR"):
            return False
            
        # Check for TERM environment variable
        term = os.environ.get("TERM", "").lower()
        if term in ["dumb", "unknown"]:
            return False
            
        return True
        
    def print_check(self, message: str) -> None:
        """Print a checkmark message in green.
        
        Args:
            message: Message to print
        """
        print(f"{self.bold_green}✓{self.reset} {self.bold}{message}{self.reset}", file=sys.stderr)
        
    def print_warning(self, message: str) -> None:
        """Print a warning message in yellow.
        
        Args:
            message: Message to print
        """
        print(f"{self.bold_yellow}⚠{self.reset} {self.bold}{message}{self.reset}", file=sys.stderr)
        
    def print_error(self, message: str) -> None:
        """Print an error message in red.
        
        Args:
            message: Message to print
        """
        print(f"{self.bold_red}✗{self.reset} {self.bold}{message}{self.reset}", file=sys.stderr)
        
    def print_success(self, message: str) -> None:
        """Print a success message in green.
        
        Args:
            message: Message to print
        """
        print(f"{self.green}✓{self.reset} {self.green}{message}{self.reset}", file=sys.stderr)
        
    def print_header(self, title: str) -> None:
        """Print a section header.
        
        Args:
            title: Header title
        """
        width = 80
        padding = (width - len(title)) // 2
        
        print()
        print(f"{self.bold_blue}{'=' * width}{self.reset}")
        print(f"{self.bold_blue}{' ' * padding}{title}{' ' * padding}{self.reset}")
        print(f"{self.bold_blue}{'=' * width}{self.reset}")
        print()
        
    def print_separator(self) -> None:
        """Print a separator line."""
        print(f"{self.blue}{'-' * 40}{self.reset}")
        
    def print_path(self, path: str) -> None:
        """Print a file path with highlighting.
        
        Args:
            path: Path to print
        """
        print(f"{self.bold_cyan}{path}{self.reset}")
        
    def print_stat(self, stat: str) -> None:
        """Print a statistic or measurement.
        
        Args:
            stat: Statistic to print
        """
        print(f"{self.bold_magenta}{stat}{self.reset}")
        
    def format_size(self, size: int) -> str:
        """Format file size for display.
        
        Args:
            size: Size in bytes
            
        Returns:
            Formatted size string
        """
        suffixes = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
        scale = 0
        
        while size > 1024 and scale < len(suffixes) - 1:
            size /= 1024
            scale += 1
            
        return f"{size:.1f} {suffixes[scale]}"
