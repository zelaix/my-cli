"""
My CLI - A Python-based AI command-line assistant.

This package provides a command-line interface for AI-powered productivity tasks
with enhanced performance and extensibility.
"""

__version__ = "0.1.0"
__author__ = "My CLI Team"
__license__ = "Apache-2.0"

from typing import Final

# Package metadata
VERSION: Final[str] = __version__
PACKAGE_NAME: Final[str] = "my-cli"
USER_AGENT: Final[str] = f"{PACKAGE_NAME}/{VERSION}"

# Re-export commonly used items
__all__ = [
    "__version__",
    "VERSION",
    "PACKAGE_NAME", 
    "USER_AGENT",
]