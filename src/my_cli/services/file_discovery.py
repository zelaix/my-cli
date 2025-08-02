"""
File discovery service for My CLI.

This module provides file discovery and management services,
mirroring the functionality of the original Gemini CLI's FileDiscoveryService.
"""

import asyncio
import fnmatch
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Set, Dict, Any
import logging
import mimetypes
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FileFilteringOptions:
    """Options for filtering files during discovery."""
    respect_git_ignore: bool = True
    respect_gemini_ignore: bool = True
    enable_recursive_file_search: bool = True


class FileDiscoveryService:
    """Service for discovering and managing files in a workspace."""
    
    # Common ignore patterns
    DEFAULT_IGNORE_PATTERNS = {
        # Version control
        '.git', '.svn', '.hg', '.bzr',
        # Dependencies
        'node_modules', '__pycache__', '.venv', 'venv', 'env',
        # Build artifacts
        'dist', 'build', '.next', '.nuxt', 'target',
        # IDE files
        '.vscode', '.idea', '*.swp', '*.swo', '*~',
        # OS files
        '.DS_Store', 'Thumbs.db', 'desktop.ini',
        # Package managers
        'package-lock.json', 'yarn.lock', 'Pipfile.lock',
    }
    
    # Common code file extensions
    CODE_EXTENSIONS = {
        '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
        '.cs', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala',
        '.sh', '.bash', '.zsh', '.ps1', '.sql', '.html', '.css', '.scss',
        '.sass', '.less', '.vue', '.svelte', '.yaml', '.yml', '.json',
        '.xml', '.toml', '.ini', '.cfg', '.conf', '.md', '.rst', '.txt'
    }
    
    def __init__(self, root_directory: str):
        """Initialize file discovery service.
        
        Args:
            root_directory: Root directory to discover files from
        """
        self.root_directory = Path(root_directory).resolve()
        self._git_ignore_patterns: Optional[Set[str]] = None
        self._gemini_ignore_patterns: Optional[Set[str]] = None
        self._cached_files: Optional[List[Path]] = None
        
    async def discover_files(
        self,
        filtering_options: Optional[FileFilteringOptions] = None,
        patterns: Optional[List[str]] = None,
        max_files: int = 10000
    ) -> List[Path]:
        """Discover files in the workspace.
        
        Args:
            filtering_options: Options for filtering files
            patterns: Glob patterns to match files
            max_files: Maximum number of files to return
            
        Returns:
            List of discovered file paths
        """
        if filtering_options is None:
            filtering_options = FileFilteringOptions()
            
        # Load ignore patterns if needed
        if filtering_options.respect_git_ignore:
            await self._load_git_ignore_patterns()
        if filtering_options.respect_gemini_ignore:
            await self._load_gemini_ignore_patterns()
        
        discovered_files = []
        
        try:
            if filtering_options.enable_recursive_file_search:
                # Recursive discovery
                for file_path in self._walk_directory(
                    self.root_directory,
                    filtering_options,
                    patterns,
                    max_files
                ):
                    discovered_files.append(file_path)
                    if len(discovered_files) >= max_files:
                        break
            else:
                # Non-recursive discovery (current directory only)
                for file_path in self.root_directory.iterdir():
                    if file_path.is_file():
                        if self._should_include_file(file_path, filtering_options, patterns):
                            discovered_files.append(file_path)
                            if len(discovered_files) >= max_files:
                                break
                                
        except Exception as e:
            logger.error(f"Error discovering files: {e}")
            
        # Sort by modification time (most recent first)
        discovered_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        self._cached_files = discovered_files
        return discovered_files
    
    def _walk_directory(
        self,
        directory: Path,
        filtering_options: FileFilteringOptions,
        patterns: Optional[List[str]],
        max_files: int,
        _current_count: int = 0
    ) -> List[Path]:
        """Recursively walk directory and yield matching files.
        
        Args:
            directory: Directory to walk
            filtering_options: Filtering options
            patterns: Glob patterns to match
            max_files: Maximum files to return
            _current_count: Current file count (for recursion)
            
        Yields:
            File paths that match criteria
        """
        try:
            for item in directory.iterdir():
                if _current_count >= max_files:
                    break
                    
                if item.is_file():
                    if self._should_include_file(item, filtering_options, patterns):
                        yield item
                        _current_count += 1
                elif item.is_dir():
                    if self._should_include_directory(item, filtering_options):
                        yield from self._walk_directory(
                            item, filtering_options, patterns, max_files, _current_count
                        )
                        
        except PermissionError:
            logger.warning(f"Permission denied accessing directory: {directory}")
        except Exception as e:
            logger.error(f"Error walking directory {directory}: {e}")
    
    def _should_include_file(
        self,
        file_path: Path,
        filtering_options: FileFilteringOptions,
        patterns: Optional[List[str]] = None
    ) -> bool:
        """Check if file should be included in discovery.
        
        Args:
            file_path: Path to check
            filtering_options: Filtering options
            patterns: Optional glob patterns to match
            
        Returns:
            True if file should be included
        """
        # Skip if file doesn't exist or is not a regular file
        if not file_path.is_file():
            return False
            
        # Check against patterns if provided
        if patterns:
            matched = False
            for pattern in patterns:
                if fnmatch.fnmatch(file_path.name, pattern) or \
                   fnmatch.fnmatch(str(file_path), pattern):
                    matched = True
                    break
            if not matched:
                return False
        
        # Check default ignore patterns
        if self._matches_ignore_patterns(file_path, self.DEFAULT_IGNORE_PATTERNS):
            return False
            
        # Check git ignore patterns
        if filtering_options.respect_git_ignore and self._git_ignore_patterns:
            if self._matches_ignore_patterns(file_path, self._git_ignore_patterns):
                return False
                
        # Check gemini ignore patterns
        if filtering_options.respect_gemini_ignore and self._gemini_ignore_patterns:
            if self._matches_ignore_patterns(file_path, self._gemini_ignore_patterns):
                return False
        
        return True
    
    def _should_include_directory(
        self,
        directory: Path,
        filtering_options: FileFilteringOptions
    ) -> bool:
        """Check if directory should be traversed.
        
        Args:
            directory: Directory path to check
            filtering_options: Filtering options
            
        Returns:
            True if directory should be traversed
        """
        # Check default ignore patterns
        if self._matches_ignore_patterns(directory, self.DEFAULT_IGNORE_PATTERNS):
            return False
            
        # Check git ignore patterns
        if filtering_options.respect_git_ignore and self._git_ignore_patterns:
            if self._matches_ignore_patterns(directory, self._git_ignore_patterns):
                return False
                
        # Check gemini ignore patterns  
        if filtering_options.respect_gemini_ignore and self._gemini_ignore_patterns:
            if self._matches_ignore_patterns(directory, self._gemini_ignore_patterns):
                return False
        
        return True
    
    def _matches_ignore_patterns(self, path: Path, patterns: Set[str]) -> bool:
        """Check if path matches any ignore patterns.
        
        Args:
            path: Path to check
            patterns: Set of ignore patterns
            
        Returns:
            True if path matches any pattern
        """
        path_str = str(path.relative_to(self.root_directory))
        name = path.name
        
        for pattern in patterns:
            # Direct name match
            if fnmatch.fnmatch(name, pattern):
                return True
            # Full path match
            if fnmatch.fnmatch(path_str, pattern):
                return True
            # Directory pattern match
            if pattern.endswith('/') and fnmatch.fnmatch(path_str + '/', pattern):
                return True
                
        return False
    
    async def _load_git_ignore_patterns(self) -> None:
        """Load patterns from .gitignore files."""
        if self._git_ignore_patterns is not None:
            return
            
        patterns = set()
        
        # Load global gitignore
        try:
            result = await asyncio.create_subprocess_exec(
                'git', 'config', '--global', 'core.excludesfile',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            if result.returncode == 0:
                global_gitignore = Path(stdout.decode().strip()).expanduser()
                if global_gitignore.exists():
                    patterns.update(self._parse_gitignore_file(global_gitignore))
        except Exception:
            pass  # Ignore errors loading global gitignore
        
        # Load local gitignore files
        for gitignore_path in self.root_directory.rglob('.gitignore'):
            try:
                patterns.update(self._parse_gitignore_file(gitignore_path))
            except Exception as e:
                logger.warning(f"Error loading .gitignore file {gitignore_path}: {e}")
        
        self._git_ignore_patterns = patterns
    
    async def _load_gemini_ignore_patterns(self) -> None:
        """Load patterns from .my-cli-ignore files."""
        if self._gemini_ignore_patterns is not None:
            return
            
        patterns = set()
        
        for ignore_path in self.root_directory.rglob('.my-cli-ignore'):
            try:
                patterns.update(self._parse_gitignore_file(ignore_path))
            except Exception as e:
                logger.warning(f"Error loading .my-cli-ignore file {ignore_path}: {e}")
        
        self._gemini_ignore_patterns = patterns
    
    def _parse_gitignore_file(self, file_path: Path) -> Set[str]:
        """Parse a gitignore-style file and return patterns.
        
        Args:
            file_path: Path to gitignore file
            
        Returns:
            Set of ignore patterns
        """
        patterns = set()
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    # Remove negation for simplicity (!)
                    if line.startswith('!'):
                        continue
                    patterns.add(line)
        except Exception as e:
            logger.error(f"Error reading ignore file {file_path}: {e}")
            
        return patterns
    
    async def find_files_by_pattern(
        self,
        pattern: str,
        filtering_options: Optional[FileFilteringOptions] = None,
        max_files: int = 1000
    ) -> List[Path]:
        """Find files matching a specific pattern.
        
        Args:
            pattern: Glob pattern to match
            filtering_options: Options for filtering files
            max_files: Maximum number of files to return
            
        Returns:
            List of matching file paths
        """
        return await self.discover_files(
            filtering_options=filtering_options,
            patterns=[pattern],
            max_files=max_files
        )
    
    async def get_file_content(
        self,
        file_path: Path,
        max_size: int = 1024 * 1024  # 1MB default
    ) -> Optional[str]:
        """Get content of a file.
        
        Args:
            file_path: Path to file
            max_size: Maximum file size to read
            
        Returns:
            File content as string or None if error
        """
        try:
            if not file_path.exists() or not file_path.is_file():
                return None
                
            stat = file_path.stat()
            if stat.st_size > max_size:
                logger.warning(f"File {file_path} is too large ({stat.st_size} bytes)")
                return None
            
            # Try to determine encoding
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if mime_type and not mime_type.startswith('text/'):
                # Skip binary files
                return None
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Get information about a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file information
        """
        try:
            stat = file_path.stat()
            mime_type, _ = mimetypes.guess_type(str(file_path))
            
            return {
                'path': str(file_path),
                'name': file_path.name,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'is_code_file': file_path.suffix.lower() in self.CODE_EXTENSIONS,
                'mime_type': mime_type,
                'extension': file_path.suffix,
                'relative_path': str(file_path.relative_to(self.root_directory))
            }
        except Exception as e:
            logger.error(f"Error getting file info for {file_path}: {e}")
            return {
                'path': str(file_path),
                'name': file_path.name,
                'error': str(e)
            }
    
    def clear_cache(self) -> None:
        """Clear cached file listings."""
        self._cached_files = None
        self._git_ignore_patterns = None
        self._gemini_ignore_patterns = None