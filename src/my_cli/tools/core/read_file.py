"""ReadFile tool implementation for reading files with offset/limit support."""

import asyncio
import os
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

from ..base import ReadOnlyTool
from ..types import Icon, ToolLocation, ToolResult
# Avoid circular import


class ReadFileToolParams:
    """Parameters for the ReadFile tool."""
    absolute_path: str
    offset: Optional[int] = None
    limit: Optional[int] = None


class ReadFileTool(ReadOnlyTool):
    """Tool for reading file contents with pagination support."""
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "absolute_path": {
                    "type": "string",
                    "description": "The absolute path to the file to read"
                },
                "offset": {
                    "type": "integer",
                    "description": "Optional: Line number to start reading from (0-based)",
                    "minimum": 0
                },
                "limit": {
                    "type": "integer", 
                    "description": "Optional: Maximum number of lines to read",
                    "minimum": 1
                }
            },
            "required": ["absolute_path"]
        }
        
        super().__init__(
            name="read_file",
            display_name="Read File",
            description="Reads and returns the content of a specified file from the local filesystem. Handles text, images (PNG, JPG, GIF, WEBP, SVG, BMP), and PDF files. For text files, it can read specific line ranges.",
            icon=Icon.FILE_SEARCH,
            schema=schema,
            config=config
        )
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate ReadFile parameters."""
        absolute_path = params.get("absolute_path")
        if not absolute_path:
            return "absolute_path parameter is required"
        
        # Convert relative paths to absolute paths
        if not os.path.isabs(absolute_path):
            absolute_path = os.path.abspath(absolute_path)
            # Update the params with the absolute path
            params["absolute_path"] = absolute_path
        
        # Validate workspace path
        workspace_error = self._validate_workspace_path(absolute_path)
        if workspace_error:
            return workspace_error
        
        # Check if file exists
        if not os.path.exists(absolute_path):
            return f"File does not exist: {absolute_path}"
        
        if not os.path.isfile(absolute_path):
            return f"Path is not a file: {absolute_path}"
        
        # Validate offset and limit
        offset = params.get("offset")
        limit = params.get("limit")
        
        if offset is not None and offset < 0:
            return "offset must be non-negative"
        
        if limit is not None and limit <= 0:
            return "limit must be positive"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get description of what this tool will do."""
        path = params.get("absolute_path", "<unknown>")
        relative_path = self._get_relative_path(path)
        
        offset = params.get("offset")
        limit = params.get("limit")
        
        if offset is not None or limit is not None:
            range_desc = ""
            if offset is not None:
                range_desc += f" starting from line {offset + 1}"
            if limit is not None:
                range_desc += f" (max {limit} lines)"
            return f"Read {relative_path}{range_desc}"
        
        return f"Read {relative_path}"
    
    def tool_locations(self, params: Dict[str, Any]) -> List[ToolLocation]:
        """Get the file location that will be read."""
        path = params.get("absolute_path")
        offset = params.get("offset")
        
        if path:
            return [ToolLocation(path=path, line=offset)]
        return []
    
    async def execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event,
        update_callback: Optional[callable] = None
    ) -> ToolResult:
        """Execute the ReadFile tool."""
        # Validate parameters
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return self.create_result(
                llm_content=f"Error: {validation_error}",
                return_display=validation_error,
                success=False,
                error=validation_error
            )
        
        file_path = params["absolute_path"]
        offset = params.get("offset")
        limit = params.get("limit")
        
        try:
            # Check if we should abort
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Operation was cancelled",
                    return_display="Operation cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            # Determine file type
            mime_type, _ = mimetypes.guess_type(file_path)
            
            # Handle binary files (images, etc.)
            if mime_type and (mime_type.startswith('image/') or mime_type == 'application/pdf'):
                return await self._read_binary_file(file_path, mime_type)
            
            # Handle text files
            return await self._read_text_file(file_path, offset, limit, abort_signal)
        
        except Exception as e:
            error_msg = f"Error reading file: {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False,
                error=str(e)
            )
    
    async def _read_text_file(
        self,
        file_path: str,
        offset: Optional[int],
        limit: Optional[int],
        abort_signal: asyncio.Event
    ) -> ToolResult:
        """Read a text file with optional offset and limit."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if offset is None and limit is None:
                    # Read entire file
                    content = f.read()
                    
                    # Check for abort during read
                    if abort_signal.is_set():
                        return self.create_result(
                            llm_content="Operation was cancelled",
                            success=False,
                            error="Operation cancelled"
                        )
                else:
                    # Read with pagination
                    lines = f.readlines()
                    
                    start_line = offset or 0
                    end_line = start_line + (limit or len(lines))
                    
                    if start_line >= len(lines):
                        content = "(File has fewer lines than the specified offset)"
                    else:
                        selected_lines = lines[start_line:end_line]
                        content = ''.join(selected_lines)
            
            # Create formatted content for LLM
            relative_path = self._get_relative_path(file_path)
            
            # Add line numbers if reading with offset/limit
            if offset is not None or limit is not None:
                lines = content.split('\n')
                start_line_num = (offset or 0) + 1
                numbered_lines = []
                
                for i, line in enumerate(lines):
                    line_num = start_line_num + i
                    numbered_lines.append(f"{line_num:5d}→{line}")
                
                formatted_content = '\n'.join(numbered_lines)
            else:
                # Add line numbers for entire file
                lines = content.split('\n')
                numbered_lines = []
                
                for i, line in enumerate(lines, 1):
                    numbered_lines.append(f"{i:5d}→{line}")
                
                formatted_content = '\n'.join(numbered_lines)
            
            # Create summary
            line_count = len(content.split('\n'))
            summary = f"Read {relative_path} ({line_count} lines)"
            
            if offset is not None or limit is not None:
                actual_start = (offset or 0) + 1
                actual_end = actual_start + line_count - 1
                summary += f" [lines {actual_start}-{actual_end}]"
            
            return self.create_result(
                llm_content=formatted_content,
                return_display=f"**{summary}**\n\n```\n{formatted_content}\n```"
            )
        
        except UnicodeDecodeError:
            # Try reading as binary if UTF-8 fails
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                # Convert to hex representation for binary files
                hex_content = content.hex()
                formatted_hex = ' '.join(hex_content[i:i+2] for i in range(0, len(hex_content), 2))
                
                return self.create_result(
                    llm_content=f"Binary file content (hex): {formatted_hex[:1000]}...",
                    return_display=f"**Binary file detected**\n\nFile: {self._get_relative_path(file_path)}\nSize: {len(content)} bytes\n\nFirst 500 bytes (hex):\n```\n{formatted_hex[:1000]}\n```"
                )
            
            except Exception as e:
                raise Exception(f"Failed to read file as both text and binary: {str(e)}")
    
    async def _read_binary_file(self, file_path: str, mime_type: str) -> ToolResult:
        """Handle binary files like images and PDFs."""
        relative_path = self._get_relative_path(file_path)
        file_size = os.path.getsize(file_path)
        
        # For now, we'll just return metadata about binary files
        # In a full implementation, we could use image processing libraries
        # or PDF readers to extract text content
        
        content = f"Binary file: {relative_path}\nType: {mime_type}\nSize: {file_size} bytes"
        
        display = f"**Binary File Detected**\n\n" \
                 f"- **File**: {relative_path}\n" \
                 f"- **Type**: {mime_type}\n" \
                 f"- **Size**: {file_size:,} bytes\n\n" \
                 f"*Note: Binary file content cannot be displayed as text. " \
                 f"Use appropriate tools to view {mime_type.split('/')[0]} files.*"
        
        return self.create_result(
            llm_content=content,
            return_display=display
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
