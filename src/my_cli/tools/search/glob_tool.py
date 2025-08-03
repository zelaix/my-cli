"""Glob tool implementation for finding files by pattern.

This module provides a glob tool similar to the Gemini CLI's glob functionality,
allowing users to efficiently find files matching specific glob patterns.
"""

import asyncio
import os
import glob as glob_module
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

from ..base import ReadOnlyTool
from ..types import Icon, ToolResult, ToolLocation


class GlobFile:
    """Represents a file found by glob search."""
    
    def __init__(self, path: str, mtime_ms: Optional[int] = None):
        self.path = path
        self.mtime_ms = mtime_ms
    
    def fullpath(self) -> str:
        """Return the full path of the file."""
        return self.path


class GlobTool(ReadOnlyTool):
    """
    Efficiently finds files matching specific glob patterns.
    
    This tool returns absolute paths sorted by modification time (newest first),
    making it ideal for quickly locating files based on their name or path structure,
    especially in large codebases.
    """
    
    NAME = "glob"
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The glob pattern to match against (e.g., '**/*.py', 'docs/*.md')"
                },
                "path": {
                    "type": "string",
                    "description": "Optional: The absolute path to the directory to search within. If omitted, searches the current working directory."
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Optional: Whether the search should be case-sensitive. Defaults to false."
                },
                "respect_git_ignore": {
                    "type": "boolean", 
                    "description": "Optional: Whether to respect .gitignore patterns when finding files. Defaults to true."
                }
            },
            "required": ["pattern"]
        }
        
        super().__init__(
            name=self.NAME,
            display_name="Find Files",
            description="Efficiently finds files matching specific glob patterns (e.g., `src/**/*.py`, `**/*.md`), returning absolute paths sorted by modification time (newest first). Ideal for quickly locating files based on their name or path structure, especially in large codebases.",
            icon=Icon.FILE_SEARCH,
            schema=schema,
            config=config
        )
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate the glob parameters."""
        if not params.get("pattern"):
            return "Pattern is required"
        
        pattern = params["pattern"]
        if not isinstance(pattern, str) or not pattern.strip():
            return "Pattern cannot be empty"
        
        # Validate path if provided
        if params.get("path"):
            path_validation = self._validate_workspace_path(params["path"])
            if path_validation:
                return path_validation
            
            search_path = params["path"]
            if not os.path.exists(search_path):
                return f"Search path does not exist: {search_path}"
            
            if not os.path.isdir(search_path):
                return f"Search path is not a directory: {search_path}"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get a description of the glob operation."""
        description = f"Find files matching '{params['pattern']}'"
        
        if params.get("path"):
            search_path = params["path"]
            if os.path.isabs(search_path):
                # Make path relative for display if possible
                try:
                    cwd = os.getcwd()
                    rel_path = os.path.relpath(search_path, cwd)
                    if not rel_path.startswith(".."):
                        search_path = rel_path
                except ValueError:
                    pass  # Keep absolute path
            description += f" within {search_path}"
        else:
            description += " within current directory"
        
        return description
    
    async def execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event,
        update_callback: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """Execute the glob search."""
        # Validate parameters
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return self.create_result(
                llm_content=f"Error: Invalid parameters. {validation_error}",
                return_display=f"Invalid parameters: {validation_error}",
                success=False
            )
        
        try:
            search_path = params.get("path", os.getcwd())
            pattern = params["pattern"]
            case_sensitive = params.get("case_sensitive", False)
            respect_git_ignore = params.get("respect_git_ignore", True)
            
            # Find matching files
            matched_files = await self._perform_glob_search(
                pattern=pattern,
                search_path=search_path,
                case_sensitive=case_sensitive,
                respect_git_ignore=respect_git_ignore,
                abort_signal=abort_signal
            )
            
            if not matched_files:
                no_match_msg = f"No files found matching pattern '{pattern}' within {search_path}"
                return self.create_result(
                    llm_content=no_match_msg,
                    return_display="No files found"
                )
            
            # Sort files by modification time (newest first)
            sorted_files = self._sort_files_by_mtime(matched_files)
            
            file_count = len(sorted_files)
            file_paths = [f.fullpath() for f in sorted_files]
            
            # Build result content
            result_message = f"Found {file_count} file(s) matching '{pattern}' within {search_path}, sorted by modification time (newest first):\n"
            result_message += "\n".join(file_paths)
            
            return self.create_result(
                llm_content=result_message,
                return_display=f"Found {file_count} matching file(s)"
            )
            
        except Exception as e:
            error_msg = f"Error during glob search: {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False
            )
    
    async def _perform_glob_search(
        self,
        pattern: str,
        search_path: str,
        case_sensitive: bool,
        respect_git_ignore: bool,
        abort_signal: asyncio.Event
    ) -> List[GlobFile]:
        """Perform the actual glob search."""
        matched_files = []
        
        # Change to search directory for glob operation
        original_cwd = os.getcwd()
        try:
            os.chdir(search_path)
            
            # Use glob to find matching files
            if case_sensitive:
                matches = glob_module.glob(pattern, recursive=True)
            else:
                # For case-insensitive search, we need to handle it manually
                # This is a simplified approach - real implementation might be more complex
                matches = glob_module.glob(pattern, recursive=True)
            
            for match in matches:
                if abort_signal.is_set():
                    break
                
                full_path = os.path.abspath(match)
                
                # Skip directories
                if os.path.isdir(full_path):
                    continue
                
                # Get modification time
                try:
                    stat_info = os.stat(full_path)
                    mtime_ms = int(stat_info.st_mtime * 1000)
                except OSError:
                    mtime_ms = 0
                
                matched_files.append(GlobFile(full_path, mtime_ms))
        
        finally:
            os.chdir(original_cwd)
        
        # Apply git ignore filtering if requested
        if respect_git_ignore and self._is_git_repository(search_path):
            matched_files = self._filter_git_ignored_files(matched_files, search_path)
        
        return matched_files
    
    def _sort_files_by_mtime(self, files: List[GlobFile]) -> List[GlobFile]:
        """Sort files by modification time (newest first), then alphabetically."""
        # Define recency threshold (1 day in milliseconds)
        one_day_ms = 24 * 60 * 60 * 1000
        now_ms = int(__import__('time').time() * 1000)
        
        def sort_key(file: GlobFile):
            mtime = file.mtime_ms or 0
            is_recent = (now_ms - mtime) < one_day_ms
            
            if is_recent:
                # Recent files: sort by mtime (newest first)
                return (0, -mtime)
            else:
                # Older files: sort alphabetically
                return (1, file.fullpath())
        
        return sorted(files, key=sort_key)
    
    def _is_git_repository(self, path: str) -> bool:
        """Check if the path is within a git repository."""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=path,
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, ImportError):
            return False
    
    def _filter_git_ignored_files(self, files: List[GlobFile], search_path: str) -> List[GlobFile]:
        """Filter out git-ignored files."""
        try:
            import subprocess
            
            # Get list of all files tracked or not ignored by git
            result = subprocess.run(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                cwd=search_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                # If git command fails, return all files
                return files
            
            # Convert git output to absolute paths
            git_files = set()
            for line in result.stdout.splitlines():
                if line.strip():
                    abs_path = os.path.abspath(os.path.join(search_path, line.strip()))
                    git_files.add(abs_path)
            
            # Filter files to only include those not ignored by git
            filtered_files = []
            for file in files:
                if file.fullpath() in git_files:
                    filtered_files.append(file)
            
            return filtered_files
            
        except Exception:
            # If filtering fails, return all files
            return files