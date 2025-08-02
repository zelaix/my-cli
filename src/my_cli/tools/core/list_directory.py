"""ListDirectory tool implementation with filtering and metadata support."""

import asyncio
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from ..base import ReadOnlyTool
from ..types import Icon, ToolLocation, ToolResult
# Avoid circular import


class ListDirectoryToolParams:
    """Parameters for the ListDirectory tool."""
    path: str
    recursive: Optional[bool] = False
    include_hidden: Optional[bool] = False
    max_depth: Optional[int] = None
    pattern: Optional[str] = None


class ListDirectoryTool(ReadOnlyTool):
    """Tool for listing directory contents with filtering options."""
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The absolute path to the directory to list"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list contents recursively",
                    "default": False
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Whether to include hidden files and directories",
                    "default": False
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum depth for recursive listing",
                    "minimum": 1
                },
                "pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to filter files (e.g., '*.py')"
                }
            },
            "required": ["path"]
        }
        
        super().__init__(
            name="list_directory",
            display_name="List Directory",
            description="Lists the contents of a directory with optional filtering, recursion, and metadata. Respects .gitignore patterns and provides file sizes, permissions, and modification times.",
            icon=Icon.FOLDER,
            schema=schema,
            config=config
        )
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate ListDirectory parameters."""
        path = params.get("path")
        if not path:
            return "path parameter is required"
        
        # Convert relative paths to absolute paths
        if not os.path.isabs(path):
            path = os.path.abspath(path)
            # Update the params with the absolute path
            params["path"] = path
        
        # Validate workspace path
        workspace_error = self._validate_workspace_path(path)
        if workspace_error:
            return workspace_error
        
        # Check if directory exists
        if not os.path.exists(path):
            return f"Directory does not exist: {path}"
        
        if not os.path.isdir(path):
            return f"Path is not a directory: {path}"
        
        # Validate max_depth
        max_depth = params.get("max_depth")
        if max_depth is not None and max_depth < 1:
            return "max_depth must be at least 1"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get description of what this tool will do."""
        path = params.get("path", "<unknown>")
        relative_path = self._get_relative_path(path)
        
        desc = f"List contents of {relative_path}"
        
        if params.get("recursive"):
            desc += " (recursive)"
            
            max_depth = params.get("max_depth")
            if max_depth:
                desc += f" up to depth {max_depth}"
        
        pattern = params.get("pattern")
        if pattern:
            desc += f" matching '{pattern}'"
        
        if params.get("include_hidden"):
            desc += " including hidden files"
        
        return desc
    
    def tool_locations(self, params: Dict[str, Any]) -> List[ToolLocation]:
        """Get the directory location that will be listed."""
        path = params.get("path")
        if path:
            return [ToolLocation(path=path)]
        return []
    
    async def execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event,
        update_callback: Optional[callable] = None
    ) -> ToolResult:
        """Execute the ListDirectory tool."""
        # Validate parameters
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return self.create_result(
                llm_content=f"Error: {validation_error}",
                return_display=validation_error,
                success=False,
                error=validation_error
            )
        
        directory_path = params["path"]
        recursive = params.get("recursive", False)
        include_hidden = params.get("include_hidden", False)
        max_depth = params.get("max_depth")
        pattern = params.get("pattern")
        
        try:
            # Check if we should abort
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Operation was cancelled",
                    return_display="Operation cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            if recursive:
                entries = await self._list_recursive(
                    directory_path,
                    include_hidden,
                    max_depth,
                    pattern,
                    abort_signal
                )
            else:
                entries = await self._list_single_directory(
                    directory_path,
                    include_hidden,
                    pattern,
                    abort_signal
                )
            
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Operation was cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            # Sort entries: directories first, then files, both alphabetically
            entries.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))
            
            # Create formatted output
            return self._format_results(directory_path, entries, recursive)
        
        except Exception as e:
            error_msg = f"Error listing directory: {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False,
                error=str(e)
            )
    
    async def _list_single_directory(
        self,
        directory_path: str,
        include_hidden: bool,
        pattern: Optional[str],
        abort_signal: asyncio.Event
    ) -> List[Dict[str, Any]]:
        """List contents of a single directory."""
        entries = []
        
        try:
            for item in os.listdir(directory_path):
                if abort_signal.is_set():
                    break
                
                # Skip hidden files if not requested
                if not include_hidden and item.startswith('.'):
                    continue
                
                # Apply pattern filter
                if pattern and not self._matches_pattern(item, pattern):
                    continue
                
                item_path = os.path.join(directory_path, item)
                entry = await self._get_entry_info(item_path, item)
                entries.append(entry)
        
        except PermissionError:
            # Handle permission denied gracefully
            entries.append({
                'name': '(Permission denied)',
                'type': 'error',
                'size': 0,
                'modified': '',
                'permissions': '',
                'path': directory_path
            })
        
        return entries
    
    async def _list_recursive(
        self,
        directory_path: str,
        include_hidden: bool,
        max_depth: Optional[int],
        pattern: Optional[str],
        abort_signal: asyncio.Event,
        current_depth: int = 0
    ) -> List[Dict[str, Any]]:
        """List directory contents recursively."""
        entries = []
        
        # Check depth limit
        if max_depth is not None and current_depth >= max_depth:
            return entries
        
        try:
            for item in os.listdir(directory_path):
                if abort_signal.is_set():
                    break
                
                # Skip hidden files if not requested
                if not include_hidden and item.startswith('.'):
                    continue
                
                item_path = os.path.join(directory_path, item)
                
                # Get entry info
                entry = await self._get_entry_info(item_path, item)
                entry['depth'] = current_depth
                
                # Apply pattern filter
                if pattern is None or self._matches_pattern(item, pattern):
                    entries.append(entry)
                
                # Recurse into directories
                if os.path.isdir(item_path) and not os.path.islink(item_path):
                    try:
                        sub_entries = await self._list_recursive(
                            item_path,
                            include_hidden,
                            max_depth,
                            pattern,
                            abort_signal,
                            current_depth + 1
                        )
                        entries.extend(sub_entries)
                    except PermissionError:
                        # Add permission error entry
                        entries.append({
                            'name': f'{item}/(Permission denied)',
                            'type': 'error',
                            'size': 0,
                            'modified': '',
                            'permissions': '',
                            'path': item_path,
                            'depth': current_depth + 1
                        })
        
        except PermissionError:
            entries.append({
                'name': '(Permission denied)',
                'type': 'error',
                'size': 0,
                'modified': '',
                'permissions': '',
                'path': directory_path,
                'depth': current_depth
            })
        
        return entries
    
    async def _get_entry_info(self, item_path: str, item_name: str) -> Dict[str, Any]:
        """Get detailed information about a file or directory."""
        try:
            stat_info = os.stat(item_path)
            
            # Determine type
            if os.path.isdir(item_path):
                entry_type = 'directory'
            elif os.path.islink(item_path):
                entry_type = 'symlink'
            else:
                entry_type = 'file'
            
            # Format size
            size = stat_info.st_size
            size_str = self._format_size(size)
            
            # Format modification time
            mtime = datetime.fromtimestamp(stat_info.st_mtime)
            modified_str = mtime.strftime('%Y-%m-%d %H:%M:%S')
            
            # Format permissions
            permissions = stat.filemode(stat_info.st_mode)
            
            return {
                'name': item_name,
                'type': entry_type,
                'size': size,
                'size_str': size_str,
                'modified': modified_str,
                'permissions': permissions,
                'path': item_path
            }
        
        except (OSError, IOError):
            return {
                'name': item_name,
                'type': 'unknown',
                'size': 0,
                'size_str': '?',
                'modified': '?',
                'permissions': '?',
                'path': item_path
            }
    
    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches the given glob pattern."""
        import fnmatch
        return fnmatch.fnmatch(filename, pattern)
    
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable form."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                if unit == 'B':
                    return f"{size} {unit}"
                else:
                    return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def _format_results(
        self,
        directory_path: str,
        entries: List[Dict[str, Any]],
        recursive: bool
    ) -> ToolResult:
        """Format the directory listing results."""
        relative_path = self._get_relative_path(directory_path)
        
        if not entries:
            content = f"Directory {relative_path} is empty"
            display = f"**Directory: {relative_path}**\n\n*Directory is empty*"
            return self.create_result(llm_content=content, return_display=display)
        
        # Count totals
        file_count = sum(1 for e in entries if e['type'] == 'file')
        dir_count = sum(1 for e in entries if e['type'] == 'directory')
        total_size = sum(e['size'] for e in entries if e['type'] == 'file')
        
        # Create LLM content (structured)
        llm_lines = [f"Directory listing: {relative_path}"]
        llm_lines.append(f"Total: {file_count} files, {dir_count} directories")
        if file_count > 0:
            llm_lines.append(f"Total size: {self._format_size(total_size)}")
        llm_lines.append("")
        
        for entry in entries:
            if recursive and 'depth' in entry:
                indent = "  " * entry['depth']
            else:
                indent = ""
            
            type_indicator = "/" if entry['type'] == 'directory' else "@" if entry['type'] == 'symlink' else ""
            llm_lines.append(
                f"{indent}{entry['name']}{type_indicator} "
                f"[{entry['type']}, {entry['size_str']}, {entry['modified']}, {entry['permissions']}]"
            )
        
        llm_content = "\n".join(llm_lines)
        
        # Create display content (formatted table)
        display_lines = [f"**Directory: {relative_path}**\n"]
        display_lines.append(f"📁 {dir_count} directories, 📄 {file_count} files")
        if file_count > 0:
            display_lines.append(f"💾 Total size: {self._format_size(total_size)}")
        display_lines.append("\n```")
        
        # Table header
        if recursive:
            display_lines.append("Name                          Type      Size       Modified            Perms")
            display_lines.append("-" * 80)
        else:
            display_lines.append("Name                     Type      Size       Modified            Perms")
            display_lines.append("-" * 75)
        
        for entry in entries:
            if recursive and 'depth' in entry:
                indent = "  " * entry['depth']
                name_width = 25 - len(indent)
            else:
                indent = ""
                name_width = 20
            
            type_indicator = "/" if entry['type'] == 'directory' else "@" if entry['type'] == 'symlink' else ""
            name_display = f"{indent}{entry['name']}{type_indicator}"
            
            # Truncate long names
            if len(name_display) > name_width:
                name_display = name_display[:name_width-3] + "..."
            
            display_lines.append(
                f"{name_display:<{name_width + 5}} "
                f"{entry['type']:<9} "
                f"{entry['size_str']:<10} "
                f"{entry['modified']:<19} "
                f"{entry['permissions']}"
            )
        
        display_lines.append("```")
        display_content = "\n".join(display_lines)
        
        return self.create_result(
            llm_content=llm_content,
            return_display=display_content
        )
    
    def _get_relative_path(self, absolute_path: str) -> str:
        """Get a relative path for display purposes."""
        try:
            if self.config and hasattr(self.config, 'project_root'):
                project_root = getattr(self.config, 'project_root', os.getcwd())
                return os.path.relpath(absolute_path, project_root)
        except ValueError:
            pass  # Can't make relative, use absolute
        
        return absolute_path
