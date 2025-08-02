"""WriteFile tool implementation with atomic operations and backup support."""

import asyncio
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable

from ..base import ModifyingTool
from ..types import (
    Icon,
    ToolLocation,
    ToolResult,
    ToolCallConfirmationDetails,
    ToolConfirmationOutcome
)
# Avoid circular import


class WriteFileToolParams:
    """Parameters for the WriteFile tool."""
    absolute_path: str
    content: str
    create_backup: Optional[bool] = True
    encoding: Optional[str] = "utf-8"


class WriteFileTool(ModifyingTool):
    """Tool for writing files with atomic operations and backup support."""
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "absolute_path": {
                    "type": "string",
                    "description": "The absolute path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                },
                "create_backup": {
                    "type": "boolean",
                    "description": "Whether to create a backup of existing file",
                    "default": True
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding to use",
                    "default": "utf-8"
                }
            },
            "required": ["absolute_path", "content"]
        }
        
        super().__init__(
            name="write_file",
            display_name="Write File",
            description="Writes content to a file with atomic operations and optional backup. Creates parent directories if needed. Existing files are backed up before modification.",
            icon=Icon.WRITE,
            schema=schema,
            config=config
        )
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate WriteFile parameters."""
        absolute_path = params.get("absolute_path")
        if not absolute_path:
            return "absolute_path parameter is required"
        
        content = params.get("content")
        if content is None:  # Allow empty string
            return "content parameter is required"
        
        # Validate workspace path
        workspace_error = self._validate_workspace_path(absolute_path)
        if workspace_error:
            return workspace_error
        
        # Check if parent directory exists or can be created
        parent_dir = os.path.dirname(absolute_path)
        if parent_dir and not os.path.exists(parent_dir):
            # Check if we can create the parent directory
            try:
                os.makedirs(parent_dir, exist_ok=True)
                # Remove it since we're just validating
                if not os.listdir(parent_dir):  # Only if empty
                    os.rmdir(parent_dir)
            except (PermissionError, OSError) as e:
                return f"Cannot create parent directory {parent_dir}: {str(e)}"
        
        # Check if we can write to the file location
        if os.path.exists(absolute_path):
            if not os.path.isfile(absolute_path):
                return f"Path exists but is not a file: {absolute_path}"
            if not os.access(absolute_path, os.W_OK):
                return f"No write permission for file: {absolute_path}"
        else:
            # Check write permission on parent directory
            if parent_dir and not os.access(parent_dir, os.W_OK):
                return f"No write permission for directory: {parent_dir}"
        
        # Validate encoding
        encoding = params.get("encoding", "utf-8")
        try:
            "test".encode(encoding)
        except LookupError:
            return f"Unknown encoding: {encoding}"
        
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """Get description of what this tool will do."""
        path = params.get("absolute_path", "<unknown>")
        relative_path = self._get_relative_path(path)
        
        content = params.get("content", "")
        line_count = len(content.split('\n'))
        
        file_exists = os.path.exists(path) if path != "<unknown>" else False
        action = "Update" if file_exists else "Create"
        
        desc = f"{action} {relative_path} ({line_count} lines)"
        
        if file_exists and params.get("create_backup", True):
            desc += " with backup"
        
        return desc
    
    def tool_locations(self, params: Dict[str, Any]) -> List[ToolLocation]:
        """Get the file location that will be written."""
        path = params.get("absolute_path")
        if path:
            return [ToolLocation(path=path)]
        return []
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event
    ) -> Union[ToolCallConfirmationDetails, bool]:
        """Check if file writing needs confirmation."""
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return False  # Will fail in execute, no need to confirm
        
        file_path = params["absolute_path"]
        file_exists = os.path.exists(file_path)
        
        if not file_exists:
            # Creating new file - minimal confirmation
            return ToolCallConfirmationDetails(
                type="write",
                title="Create New File",
                description=f"Create new file: {self._get_relative_path(file_path)}",
                file_path=file_path
            )
        else:
            # Modifying existing file - show diff preview
            try:
                with open(file_path, 'r', encoding=params.get('encoding', 'utf-8')) as f:
                    current_content = f.read()
            except Exception:
                current_content = "(Could not read current file content)"
            
            new_content = params["content"]
            
            # Create a simple diff preview
            diff_preview = self._create_diff_preview(current_content, new_content)
            
            return ToolCallConfirmationDetails(
                type="write",
                title="Overwrite Existing File",
                description=f"Overwrite file: {self._get_relative_path(file_path)}",
                file_path=file_path,
                file_diff=diff_preview,
                original_content=current_content,
                new_content=new_content
            )
    
    async def execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event,
        update_callback: Optional[callable] = None
    ) -> ToolResult:
        """Execute the WriteFile tool."""
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
        content = params["content"]
        create_backup = params.get("create_backup", True)
        encoding = params.get("encoding", "utf-8")
        
        backup_path = None
        temp_file = None
        
        try:
            # Check for abort before starting
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Write operation was cancelled",
                    return_display="Operation cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            file_exists = os.path.exists(file_path)
            
            # Create parent directories if needed
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            
            # Create backup if file exists and backup is requested
            if file_exists and create_backup:
                backup_path = self._create_backup(file_path)
                if update_callback:
                    update_callback(f"Created backup: {backup_path}")
            
            # Check for abort after backup
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Write operation was cancelled after backup",
                    return_display="Operation cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            # Write to temporary file first (atomic operation)
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                encoding=encoding,
                dir=parent_dir,
                delete=False,
                prefix=f".{os.path.basename(file_path)}.tmp"
            )
            
            try:
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure data is written to disk
            finally:
                temp_file.close()
            
            # Check for abort before final move
            if abort_signal.is_set():
                os.unlink(temp_file.name)  # Clean up temp file
                return self.create_result(
                    llm_content="Write operation was cancelled during write",
                    return_display="Operation cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            # Atomically move temp file to final location
            if os.name == 'nt':  # Windows
                if file_exists:
                    os.replace(temp_file.name, file_path)
                else:
                    shutil.move(temp_file.name, file_path)
            else:  # Unix-like
                os.rename(temp_file.name, file_path)
            
            # Calculate statistics
            line_count = len(content.split('\n'))
            char_count = len(content)
            byte_count = len(content.encode(encoding))
            
            # Create result
            relative_path = self._get_relative_path(file_path)
            action = "Updated" if file_exists else "Created"
            
            llm_content_parts = [
                f"{action} file: {file_path}",
                f"Lines: {line_count}",
                f"Characters: {char_count}",
                f"Bytes: {byte_count}",
                f"Encoding: {encoding}"
            ]
            
            if backup_path:
                llm_content_parts.append(f"Backup created: {backup_path}")
            
            llm_content = "\n".join(llm_content_parts)
            
            # Create display content
            display_parts = [f"**{action} {relative_path}**\n"]
            display_parts.append(f"📄 {line_count} lines, {char_count} characters, {byte_count} bytes")
            
            if backup_path:
                backup_relative = self._get_relative_path(backup_path)
                display_parts.append(f"💾 Backup: {backup_relative}")
            
            display_parts.append(f"✨ Encoding: {encoding}")
            
            # Show content preview if reasonable size
            if line_count <= 20 and char_count <= 1000:
                display_parts.append("\n**Content Preview:**")
                display_parts.append("```")
                display_parts.append(content)
                display_parts.append("```")
            elif line_count > 20:
                # Show first and last few lines
                lines = content.split('\n')
                preview_lines = lines[:5] + ['...'] + lines[-5:]
                display_parts.append("\n**Content Preview (truncated):**")
                display_parts.append("```")
                display_parts.append('\n'.join(preview_lines))
                display_parts.append("```")
            
            display_content = "\n".join(display_parts)
            
            return self.create_result(
                llm_content=llm_content,
                return_display=display_content
            )
        
        except Exception as e:
            # Clean up on error
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass
            
            error_msg = f"Error writing file: {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False,
                error=str(e)
            )
    
    def _create_backup(self, file_path: str) -> str:
        """Create a backup of the existing file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.backup.{timestamp}"
        
        # If backup already exists, add a counter
        counter = 1
        while os.path.exists(backup_path):
            backup_path = f"{file_path}.backup.{timestamp}.{counter}"
            counter += 1
        
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def _create_diff_preview(self, old_content: str, new_content: str) -> str:
        """Create a simple diff preview."""
        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')
        
        # Simple line-by-line comparison
        diff_lines = []
        max_lines = max(len(old_lines), len(new_lines))
        
        changes = 0
        for i in range(min(max_lines, 10)):  # Show first 10 lines of diff
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""
            
            if old_line != new_line:
                changes += 1
                if old_line:
                    diff_lines.append(f"- {old_line}")
                if new_line:
                    diff_lines.append(f"+ {new_line}")
            else:
                diff_lines.append(f"  {old_line}")
        
        if max_lines > 10:
            diff_lines.append(f"... ({max_lines - 10} more lines)")
        
        if changes == 0:
            return "No changes detected"
        
        return f"Changes detected ({changes} modified lines):\n" + "\n".join(diff_lines)
    
    def _get_relative_path(self, absolute_path: str) -> str:
        """Get a relative path for display purposes."""
        try:
            if self.config and hasattr(self.config, 'project_root'):
                project_root = getattr(self.config, 'project_root', os.getcwd())
                return os.path.relpath(absolute_path, project_root)
        except ValueError:
            pass  # Can't make relative, use absolute
        
        return absolute_path
