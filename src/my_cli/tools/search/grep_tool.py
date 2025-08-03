"""Grep tool implementation for searching file contents.

This module provides a grep tool similar to the Gemini CLI's grep functionality,
allowing users to search for patterns within file contents using regular expressions.
"""

import asyncio
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

from ..base import ReadOnlyTool
from ..types import Icon, ToolResult, ToolLocation


class GrepToolParams:
    """Parameters for the grep tool."""
    
    def __init__(self, pattern: str, path: Optional[str] = None, include: Optional[str] = None):
        self.pattern = pattern
        self.path = path
        self.include = include


class GrepMatch:
    """Represents a single grep match."""
    
    def __init__(self, file_path: str, line_number: int, line: str):
        self.file_path = file_path
        self.line_number = line_number
        self.line = line


class GrepTool(ReadOnlyTool):
    """
    Searches for a regular expression pattern within the content of files.
    
    This tool can search within a specified directory or the current working directory,
    and can filter files using glob patterns. It returns the lines containing matches
    along with their file paths and line numbers.
    """
    
    NAME = "grep"
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The regular expression pattern to search for within file contents"
                },
                "path": {
                    "type": "string",
                    "description": "Optional: The absolute path to the directory to search within. If omitted, searches the current working directory."
                },
                "include": {
                    "type": "string", 
                    "description": "Optional: A glob pattern to filter which files are searched (e.g., '*.py', '*.{js,ts}')."
                }
            },
            "required": ["pattern"]
        }
        
        super().__init__(
            name=self.NAME,
            display_name="Search Text",
            description="Searches for a regular expression pattern within the content of files in a specified directory. Can filter files by a glob pattern. Returns the lines containing matches, along with their file paths and line numbers.",
            icon=Icon.REGEX,
            schema=schema,
            config=config
        )
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate the grep parameters."""
        if not params.get("pattern"):
            return "Pattern is required"
        
        # Validate regex pattern
        try:
            re.compile(params["pattern"])
        except re.error as e:
            return f"Invalid regular expression pattern: {e}"
        
        # Validate path if provided
        if params.get("path"):
            path_validation = self._validate_workspace_path(params["path"])
            if path_validation:
                return path_validation
            
            if not os.path.exists(params["path"]):
                return f"Path does not exist: {params['path']}"
            
            if not os.path.isdir(params["path"]):
                return f"Path is not a directory: {params['path']}"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get a description of the grep operation."""
        description = f"Search for pattern '{params['pattern']}'"
        
        if params.get("include"):
            description += f" in {params['include']}"
        
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
        """Execute the grep search."""
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
            include_pattern = params.get("include")
            
            matches = await self._perform_grep_search(
                pattern=pattern,
                search_path=search_path,
                include_pattern=include_pattern,
                abort_signal=abort_signal
            )
            
            if not matches:
                no_match_msg = f"No matches found for pattern '{pattern}'"
                if include_pattern:
                    no_match_msg += f" (filter: '{include_pattern}')"
                return self.create_result(
                    llm_content=no_match_msg,
                    return_display="No matches found"
                )
            
            # Group matches by file
            matches_by_file = {}
            for match in matches:
                if match.file_path not in matches_by_file:
                    matches_by_file[match.file_path] = []
                matches_by_file[match.file_path].append(match)
            
            # Sort matches within each file by line number
            for file_matches in matches_by_file.values():
                file_matches.sort(key=lambda m: m.line_number)
            
            match_count = len(matches)
            match_term = "match" if match_count == 1 else "matches"
            
            # Build result content
            llm_content = f"Found {match_count} {match_term} for pattern '{pattern}'"
            if include_pattern:
                llm_content += f" (filter: '{include_pattern}')"
            llm_content += ":\n---\n"
            
            for file_path, file_matches in matches_by_file.items():
                llm_content += f"File: {file_path}\n"
                for match in file_matches:
                    trimmed_line = match.line.strip()
                    llm_content += f"L{match.line_number}: {trimmed_line}\n"
                llm_content += "---\n"
            
            return self.create_result(
                llm_content=llm_content.strip(),
                return_display=f"Found {match_count} {match_term}"
            )
            
        except Exception as e:
            error_msg = f"Error during grep search: {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False
            )
    
    async def _perform_grep_search(
        self,
        pattern: str,
        search_path: str,
        include_pattern: Optional[str],
        abort_signal: asyncio.Event
    ) -> List[GrepMatch]:
        """Perform the actual grep search using multiple strategies."""
        
        # Strategy 1: Try git grep if in a git repository
        if self._is_git_repository(search_path):
            try:
                matches = await self._git_grep_search(pattern, search_path, include_pattern, abort_signal)
                if matches is not None:
                    return matches
            except Exception as e:
                # Fall back to other methods if git grep fails
                pass
        
        # Strategy 2: Try system grep
        try:
            matches = await self._system_grep_search(pattern, search_path, include_pattern, abort_signal)
            if matches is not None:
                return matches
        except Exception as e:
            # Fall back to Python implementation
            pass
        
        # Strategy 3: Pure Python fallback
        return await self._python_grep_search(pattern, search_path, include_pattern, abort_signal)
    
    def _is_git_repository(self, path: str) -> bool:
        """Check if the path is within a git repository."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=path,
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def _git_grep_search(
        self,
        pattern: str,
        search_path: str,
        include_pattern: Optional[str],
        abort_signal: asyncio.Event
    ) -> Optional[List[GrepMatch]]:
        """Search using git grep."""
        cmd = ["git", "grep", "--untracked", "-n", "-E", "--ignore-case", pattern]
        
        if include_pattern:
            cmd.extend(["--", include_pattern])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=search_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return self._parse_grep_output(stdout.decode('utf-8'), search_path)
            elif process.returncode == 1:
                return []  # No matches
            else:
                # Error occurred, fall back to other methods
                return None
        except Exception:
            return None
    
    async def _system_grep_search(
        self,
        pattern: str,
        search_path: str,
        include_pattern: Optional[str],
        abort_signal: asyncio.Event
    ) -> Optional[List[GrepMatch]]:
        """Search using system grep."""
        cmd = ["grep", "-r", "-n", "-H", "-E"]
        
        # Add common excludes
        common_excludes = [".git", "node_modules", "bower_components", "__pycache__"]
        for exclude in common_excludes:
            cmd.extend([f"--exclude-dir={exclude}"])
        
        if include_pattern:
            cmd.extend([f"--include={include_pattern}"])
        
        cmd.extend([pattern, "."])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=search_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return self._parse_grep_output(stdout.decode('utf-8'), search_path)
            elif process.returncode == 1:
                return []  # No matches
            else:
                # Error occurred, fall back to Python implementation
                return None
        except Exception:
            return None
    
    async def _python_grep_search(
        self,
        pattern: str,
        search_path: str,
        include_pattern: Optional[str],
        abort_signal: asyncio.Event
    ) -> List[GrepMatch]:
        """Pure Python grep implementation as fallback."""
        import fnmatch
        
        regex = re.compile(pattern, re.IGNORECASE)
        matches = []
        
        # Walk through all files
        for root, dirs, files in os.walk(search_path):
            # Skip common directories
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".svn", ".hg"}]
            
            for file in files:
                if abort_signal.is_set():
                    break
                
                # Apply include pattern filter
                if include_pattern and not fnmatch.fnmatch(file, include_pattern):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    # Try to read as text file
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                rel_path = os.path.relpath(file_path, search_path)
                                matches.append(GrepMatch(rel_path, line_num, line.rstrip('\n\r')))
                except (IOError, OSError, UnicodeDecodeError):
                    # Skip files that can't be read as text
                    continue
        
        return matches
    
    def _parse_grep_output(self, output: str, base_path: str) -> List[GrepMatch]:
        """Parse the output from grep commands."""
        matches = []
        
        for line in output.splitlines():
            if not line.strip():
                continue
            
            # Parse format: filepath:line_number:line_content
            parts = line.split(':', 2)
            if len(parts) < 3:
                continue
            
            file_path = parts[0]
            try:
                line_number = int(parts[1])
            except ValueError:
                continue
            
            line_content = parts[2]
            
            # Make path relative to search directory
            if os.path.isabs(file_path):
                try:
                    file_path = os.path.relpath(file_path, base_path)
                except ValueError:
                    pass  # Keep absolute path if relative conversion fails
            
            matches.append(GrepMatch(file_path, line_number, line_content))
        
        return matches