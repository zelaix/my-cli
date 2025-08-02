"""EditFile tool implementation with diff preview and line-based editing."""

import asyncio
import os
import re
import shutil
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple, Callable

from ..base import ModifyingTool
from ..types import (
    Icon,
    ToolLocation,
    ToolResult,
    ToolCallConfirmationDetails,
    ToolEditConfirmationDetails,
    ToolConfirmationOutcome
)
# Avoid circular import


class EditFileToolParams:
    """Parameters for the EditFile tool."""
    absolute_path: str
    old_str: str
    new_str: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    create_backup: Optional[bool] = True
    encoding: Optional[str] = "utf-8"


class EditFileTool(ModifyingTool):
    """Tool for editing files with diff preview and precise modifications."""
    
    def __init__(self, config: Optional[Any] = None):
        schema = {
            "type": "object",
            "properties": {
                "absolute_path": {
                    "type": "string",
                    "description": "The absolute path to the file to edit"
                },
                "old_str": {
                    "type": "string",
                    "description": "The exact string to find and replace"
                },
                "new_str": {
                    "type": "string",
                    "description": "The replacement string"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Optional: Line number to start search (1-based)",
                    "minimum": 1
                },
                "end_line": {
                    "type": "integer",
                    "description": "Optional: Line number to end search (1-based)",
                    "minimum": 1
                },
                "create_backup": {
                    "type": "boolean",
                    "description": "Whether to create a backup before editing",
                    "default": True
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding to use",
                    "default": "utf-8"
                }
            },
            "required": ["absolute_path", "old_str", "new_str"]
        }
        
        super().__init__(
            name="edit_file",
            display_name="Edit File",
            description="Edits a file by finding and replacing specific text content. Shows diff preview before applying changes. Supports line range restrictions and creates backups.",
            icon=Icon.EDIT,
            schema=schema,
            config=config
        )
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate EditFile parameters."""
        absolute_path = params.get("absolute_path")
        if not absolute_path:
            return "absolute_path parameter is required"
        
        old_str = params.get("old_str")
        if old_str is None:
            return "old_str parameter is required"
        
        new_str = params.get("new_str")
        if new_str is None:
            return "new_str parameter is required"
        
        # Validate workspace path
        workspace_error = self._validate_workspace_path(absolute_path)
        if workspace_error:
            return workspace_error
        
        # Check if file exists
        if not os.path.exists(absolute_path):
            return f"File does not exist: {absolute_path}"
        
        if not os.path.isfile(absolute_path):
            return f"Path is not a file: {absolute_path}"
        
        if not os.access(absolute_path, os.R_OK | os.W_OK):
            return f"No read/write permission for file: {absolute_path}"
        
        # Validate line numbers
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        
        if start_line is not None and start_line < 1:
            return "start_line must be at least 1"
        
        if end_line is not None and end_line < 1:
            return "end_line must be at least 1"
        
        if start_line is not None and end_line is not None and start_line > end_line:
            return "start_line must be less than or equal to end_line"
        
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
        
        old_str = params.get("old_str", "")
        new_str = params.get("new_str", "")
        
        # Truncate strings for display
        old_preview = old_str[:50] + "..." if len(old_str) > 50 else old_str
        new_preview = new_str[:50] + "..." if len(new_str) > 50 else new_str
        
        desc = f"Edit {relative_path}: replace '{old_preview}' with '{new_preview}'"
        
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        if start_line or end_line:
            range_desc = ""
            if start_line:
                range_desc += f" from line {start_line}"
            if end_line:
                range_desc += f" to line {end_line}"
            desc += range_desc
        
        return desc
    
    def tool_locations(self, params: Dict[str, Any]) -> List[ToolLocation]:
        """Get the file location that will be edited."""
        path = params.get("absolute_path")
        start_line = params.get("start_line")
        
        if path:
            # Convert to 0-based line number for ToolLocation
            line = (start_line - 1) if start_line else None
            return [ToolLocation(path=path, line=line)]
        return []
    
    async def should_confirm_execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event
    ) -> Union[ToolCallConfirmationDetails, bool]:
        """Check if file editing needs confirmation with diff preview."""
        validation_error = self.validate_tool_params(params)
        if validation_error:
            return False  # Will fail in execute, no need to confirm
        
        file_path = params["absolute_path"]
        old_str = params["old_str"]
        new_str = params["new_str"]
        encoding = params.get("encoding", "utf-8")
        
        try:
            # Read current file content
            with open(file_path, 'r', encoding=encoding) as f:
                current_content = f.read()
            
            # Find the string to replace and create preview
            matches = self._find_replacements(current_content, params)
            
            if not matches:
                # No matches found - still show confirmation
                return ToolEditConfirmationDetails(
                    title="No Matches Found",
                    description=f"String '{old_str[:100]}...' not found in {self._get_relative_path(file_path)}",
                    file_path=file_path,
                    file_name=os.path.basename(file_path)
                )
            
            # Create diff preview
            new_content = self._apply_replacements(current_content, matches, new_str)
            diff_preview = self._create_detailed_diff(current_content, new_content, matches)
            
            return ToolEditConfirmationDetails(
                title="Confirm File Edit",
                description=f"Edit {self._get_relative_path(file_path)} ({len(matches)} replacement{'s' if len(matches) != 1 else ''})",
                file_path=file_path,
                file_name=os.path.basename(file_path),
                file_diff=diff_preview,
                original_content=current_content,
                new_content=new_content
            )
        
        except Exception as e:
            return ToolEditConfirmationDetails(
                title="Error Reading File",
                description=f"Could not read file for preview: {str(e)}",
                file_path=file_path,
                file_name=os.path.basename(file_path)
            )
    
    async def execute(
        self,
        params: Dict[str, Any],
        abort_signal: asyncio.Event,
        update_callback: Optional[callable] = None
    ) -> ToolResult:
        """Execute the EditFile tool."""
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
        old_str = params["old_str"]
        new_str = params["new_str"]
        create_backup = params.get("create_backup", True)
        encoding = params.get("encoding", "utf-8")
        
        backup_path = None
        temp_file = None
        
        try:
            # Check for abort before starting
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Edit operation was cancelled",
                    return_display="Operation cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            # Read current content
            with open(file_path, 'r', encoding=encoding) as f:
                current_content = f.read()
            
            # Find matches
            matches = self._find_replacements(current_content, params)
            
            if not matches:
                return self.create_result(
                    llm_content=f"No matches found for '{old_str}' in {file_path}",
                    return_display=f"**No Changes Made**\n\nString not found: `{old_str}`",
                    success=False,
                    error="String not found"
                )
            
            # Apply replacements
            new_content = self._apply_replacements(current_content, matches, new_str)
            
            # Check for abort after processing
            if abort_signal.is_set():
                return self.create_result(
                    llm_content="Edit operation was cancelled during processing",
                    return_display="Operation cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            # Create backup if requested
            if create_backup:
                backup_path = self._create_backup(file_path)
                if update_callback:
                    update_callback(f"Created backup: {backup_path}")
            
            # Write to temporary file first (atomic operation)
            parent_dir = os.path.dirname(file_path)
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                encoding=encoding,
                dir=parent_dir,
                delete=False,
                prefix=f".{os.path.basename(file_path)}.edit.tmp"
            )
            
            try:
                temp_file.write(new_content)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            finally:
                temp_file.close()
            
            # Check for abort before final move
            if abort_signal.is_set():
                os.unlink(temp_file.name)
                return self.create_result(
                    llm_content="Edit operation was cancelled during write",
                    return_display="Operation cancelled",
                    success=False,
                    error="Operation cancelled"
                )
            
            # Atomically replace original file
            if os.name == 'nt':  # Windows
                os.replace(temp_file.name, file_path)
            else:  # Unix-like
                os.rename(temp_file.name, file_path)
            
            # Calculate statistics
            old_lines = current_content.count('\n') + 1
            new_lines = new_content.count('\n') + 1
            line_diff = new_lines - old_lines
            
            # Create result
            relative_path = self._get_relative_path(file_path)
            
            llm_content_parts = [
                f"Edited file: {file_path}",
                f"Replacements made: {len(matches)}",
                f"Old content lines: {old_lines}",
                f"New content lines: {new_lines}",
                f"Line difference: {line_diff:+d}"
            ]
            
            if backup_path:
                llm_content_parts.append(f"Backup created: {backup_path}")
            
            # Add match details
            llm_content_parts.append("\nMatches replaced:")
            for i, (start, end, line_num) in enumerate(matches[:5], 1):  # Show first 5
                old_text = current_content[start:end]
                preview = old_text[:50] + "..." if len(old_text) > 50 else old_text
                llm_content_parts.append(f"{i}. Line {line_num}: '{preview}'")
            
            if len(matches) > 5:
                llm_content_parts.append(f"... and {len(matches) - 5} more")
            
            llm_content = "\n".join(llm_content_parts)
            
            # Create display content with diff
            display_parts = [f"**Edited {relative_path}**\n"]
            display_parts.append(f"🔄 {len(matches)} replacement{'s' if len(matches) != 1 else ''}")
            display_parts.append(f"📄 Lines: {old_lines} → {new_lines} ({line_diff:+d})")
            
            if backup_path:
                backup_relative = self._get_relative_path(backup_path)
                display_parts.append(f"💾 Backup: {backup_relative}")
            
            # Show detailed diff
            diff_preview = self._create_detailed_diff(current_content, new_content, matches)
            display_parts.append("\n**Changes Made:**")
            display_parts.append("```diff")
            display_parts.append(diff_preview)
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
            
            error_msg = f"Error editing file: {str(e)}"
            return self.create_result(
                llm_content=error_msg,
                return_display=error_msg,
                success=False,
                error=str(e)
            )
    
    def _find_replacements(self, content: str, params: Dict[str, Any]) -> List[Tuple[int, int, int]]:
        """Find all occurrences of old_str in content within specified line range."""
        old_str = params["old_str"]
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        
        lines = content.split('\n')
        matches = []
        
        # Determine search range
        search_start = (start_line - 1) if start_line else 0
        search_end = end_line if end_line else len(lines)
        
        # Convert to character positions
        char_pos = 0
        for line_num, line in enumerate(lines):
            if line_num < search_start:
                char_pos += len(line) + 1  # +1 for newline
                continue
            
            if line_num >= search_end:
                break
            
            # Find all occurrences in this line
            line_start = char_pos
            pos = 0
            while True:
                index = line.find(old_str, pos)
                if index == -1:
                    break
                
                start_pos = line_start + index
                end_pos = start_pos + len(old_str)
                matches.append((start_pos, end_pos, line_num + 1))
                pos = index + 1
            
            char_pos += len(line) + 1  # +1 for newline
        
        return matches
    
    def _apply_replacements(
        self,
        content: str,
        matches: List[Tuple[int, int, int]],
        new_str: str
    ) -> str:
        """Apply all replacements to content."""
        if not matches:
            return content
        
        # Sort matches by position (reverse order for safe replacement)
        sorted_matches = sorted(matches, key=lambda x: x[0], reverse=True)
        
        result = content
        for start, end, _ in sorted_matches:
            result = result[:start] + new_str + result[end:]
        
        return result
    
    def _create_detailed_diff(
        self,
        old_content: str,
        new_content: str,
        matches: List[Tuple[int, int, int]]
    ) -> str:
        """Create a detailed diff showing the changes."""
        old_lines = old_content.split('\n')
        new_lines = new_content.split('\n')
        
        diff_lines = []
        
        # Group matches by line number
        lines_with_changes = set(match[2] for match in matches)
        
        # Show context around changes
        for line_num in sorted(lines_with_changes):
            # Show some context
            start_context = max(0, line_num - 3)
            end_context = min(len(old_lines), line_num + 2)
            
            if diff_lines and diff_lines[-1] != "...":
                diff_lines.append("...")
            
            for i in range(start_context, end_context):
                line_idx = i  # Convert to 0-based
                if i + 1 == line_num:  # This line has changes
                    if line_idx < len(old_lines):
                        diff_lines.append(f"- {old_lines[line_idx]}")
                    if line_idx < len(new_lines):
                        diff_lines.append(f"+ {new_lines[line_idx]}")
                else:  # Context line
                    if line_idx < len(old_lines):
                        diff_lines.append(f"  {old_lines[line_idx]}")
        
        return "\n".join(diff_lines)
    
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
    
    def _get_relative_path(self, absolute_path: str) -> str:
        """Get a relative path for display purposes."""
        try:
            if self.config and hasattr(self.config, 'project_root'):
                project_root = getattr(self.config, 'project_root', os.getcwd())
                return os.path.relpath(absolute_path, project_root)
        except ValueError:
            pass  # Can't make relative, use absolute
        
        return absolute_path
