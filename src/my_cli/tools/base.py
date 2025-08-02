"""Enhanced base tool system for My CLI Phase 2.2.

This module provides the core interfaces and base classes for implementing tools,
following the architecture of the original Gemini CLI's tool system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar
import asyncio
import os
from pathlib import Path

from .types import (
    Icon,
    Tool,
    ToolLocation,
    ToolResult,
    ToolCallConfirmationDetails,
    ToolConfirmationOutcome
)
# Avoid circular import - config will be passed as parameter

P = TypeVar('P', bound=Dict[str, Any])  # Parameter type


class BaseTool(Tool):
    """
    Enhanced base implementation for tools with common functionality.
    
    This provides a foundation that concrete tools can build upon,
    following the original Gemini CLI's BaseTool pattern.
    """
    
    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        icon: Icon,
        schema: Dict[str, Any],
        is_output_markdown: bool = True,
        can_update_output: bool = False,
        config: Optional[Any] = None
    ):
        super().__init__(
            name=name,
            display_name=display_name,
            description=description,
            icon=icon,
            schema=schema,
            is_output_markdown=is_output_markdown,
            can_update_output=can_update_output
        )
        self.config = config
    
    def validate_tool_params(self, params: P) -> Optional[str]:
        """
        Default parameter validation using JSON schema.
        
        Override this method in concrete tools for additional validation.
        """
        # Basic type checking could be done here
        # For now, assume params are valid if they match expected structure
        return None
    
    def get_description(self, params: P) -> str:
        """
        Default description generator.
        
        Override this method in concrete tools for better descriptions.
        """
        return f"Execute {self.display_name}"
    
    def tool_locations(self, params: P) -> List[ToolLocation]:
        """
        Default implementation returns empty list.
        
        Override this method in tools that affect file system locations.
        """
        return []
    
    async def should_confirm_execute(
        self,
        params: P,
        abort_signal: asyncio.Event
    ) -> Union[ToolCallConfirmationDetails, bool]:
        """
        Default implementation - no confirmation required.
        
        Override this method in tools that need user confirmation.
        """
        return False
    
    @abstractmethod
    async def execute(
        self,
        params: P,
        abort_signal: asyncio.Event,
        update_callback: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """
        Abstract method that concrete tools must implement.
        
        This is where the actual tool logic goes.
        """
        pass
    
    def create_result(
        self,
        llm_content: Union[str, List[Dict[str, Any]]],
        return_display: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> ToolResult:
        """
        Helper method to create a ToolResult.
        
        Args:
            llm_content: Content for LLM consumption
            return_display: Display content for user
            success: Whether execution was successful
            error: Error message if failed
            
        Returns:
            ToolResult instance
        """
        return ToolResult(
            llm_content=llm_content,
            return_display=return_display,
            success=success,
            error=error
        )
    
    def _validate_workspace_path(self, file_path: str) -> Optional[str]:
        """
        Validate that a file path is within the workspace.
        
        Args:
            file_path: Path to validate
            
        Returns:
            Error message if invalid, None if valid
        """
        if not file_path:
            return "File path cannot be empty"
        
        if not os.path.isabs(file_path):
            return f"File path must be absolute: {file_path}"
        
        # Check if path is within workspace (if config available)
        if self.config:
            workspace_dirs = getattr(self.config, 'workspace_dirs', [])
            if workspace_dirs:
                path_obj = Path(file_path)
                workspace_paths = [Path(d) for d in workspace_dirs]
                
                if not any(path_obj.is_relative_to(wp) for wp in workspace_paths):
                    return f"File path must be within workspace directories: {workspace_dirs}"
        
        return None


class ReadOnlyTool(BaseTool):
    """
    Base class for read-only tools that don't modify the system.
    
    These tools typically don't require confirmation from the user.
    """
    
    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        icon: Icon,
        schema: Dict[str, Any],
        config: Optional[Any] = None
    ):
        super().__init__(name, display_name, description, icon, schema, config=config)


class ModifyingTool(BaseTool):
    """
    Base class for tools that modify the file system or execute commands.
    
    These tools typically require user confirmation before execution.
    """
    
    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        icon: Icon,
        schema: Dict[str, Any],
        config: Optional[Any] = None
    ):
        super().__init__(name, display_name, description, icon, schema, config=config)
    
    async def should_confirm_execute(
        self,
        params: P,
        abort_signal: asyncio.Event
    ) -> Union[ToolCallConfirmationDetails, bool]:
        """
        Default confirmation for modifying tools.
        
        Override this method for custom confirmation logic.
        """
        locations = self.tool_locations(params)
        if locations:
            file_paths = [loc.path for loc in locations]
            description = f"This will modify the following files: {', '.join(file_paths)}"
        else:
            description = f"This will execute: {self.get_description(params)}"
        
        return ToolCallConfirmationDetails(
            type="modify",
            title=f"Confirm {self.display_name}",
            description=description
        )