"""
Base tool system for My CLI.

This module provides the core interfaces and base classes for implementing tools,
mirroring the functionality of the original Gemini CLI's tool system.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union
from dataclasses import dataclass
from pathlib import Path
import asyncio

from pydantic import BaseModel, Field


class Icon(Enum):
    """Icons for tools in the UI."""
    FILE_SEARCH = "file_search"
    FOLDER = "folder"
    GLOBE = "globe"
    HAMMER = "hammer"
    LIGHT_BULB = "light_bulb"
    PENCIL = "pencil"
    REGEX = "regex"
    TERMINAL = "terminal"


@dataclass
class ToolLocation:
    """Represents a file system location that a tool will affect."""
    path: Path
    line: Optional[int] = None


class ToolConfirmationOutcome(Enum):
    """Outcomes for tool confirmation dialogs."""
    PROCEED_ONCE = "proceed_once"
    PROCEED_ALWAYS = "proceed_always"
    PROCEED_ALWAYS_SERVER = "proceed_always_server"
    PROCEED_ALWAYS_TOOL = "proceed_always_tool"
    MODIFY_WITH_EDITOR = "modify_with_editor"
    CANCEL = "cancel"


@dataclass
class ToolConfirmationDetails:
    """Details for tool execution confirmation."""
    type: str
    title: str
    description: str
    command: Optional[str] = None
    file_path: Optional[Path] = None
    urls: Optional[List[str]] = None


class ToolResult(BaseModel):
    """Result of a tool execution."""
    
    summary: Optional[str] = Field(
        default=None,
        description="A short, one-line summary of the tool's action and result"
    )
    
    content: str = Field(
        description="Content for LLM consumption - factual outcome of execution"
    )
    
    display: str = Field(
        description="Markdown string for user display"
    )
    
    success: bool = Field(
        default=True,
        description="Whether the tool execution was successful"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )


class Tool(Protocol):
    """
    Protocol defining the interface that all tools must implement.
    
    This mirrors the TypeScript Tool interface from the original Gemini CLI.
    """
    
    name: str
    display_name: str
    description: str
    icon: Icon
    is_output_markdown: bool
    can_update_output: bool
    
    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """
        Validate the parameters for the tool.
        
        Args:
            params: Parameters to validate
            
        Returns:
            Error message string if invalid, None if valid
        """
        ...
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """
        Get a pre-execution description of what the tool will do.
        
        Args:
            params: Parameters for the tool execution
            
        Returns:
            Markdown string describing what the tool will do
        """
        ...
    
    def get_tool_locations(self, params: Dict[str, Any]) -> List[ToolLocation]:
        """
        Determine what file system paths the tool will affect.
        
        Args:
            params: Parameters for the tool execution
            
        Returns:
            List of file system locations that will be affected
        """
        ...
    
    async def should_confirm_execute(
        self, 
        params: Dict[str, Any]
    ) -> Union[ToolConfirmationDetails, bool]:
        """
        Determine if the tool should prompt for confirmation before execution.
        
        Args:
            params: Parameters for the tool execution
            
        Returns:
            ToolConfirmationDetails if confirmation needed, False otherwise
        """
        ...
    
    async def execute(
        self, 
        params: Dict[str, Any],
        update_callback: Optional[callable] = None
    ) -> ToolResult:
        """
        Execute the tool with the given parameters.
        
        Args:
            params: Parameters for the tool execution
            update_callback: Optional callback for streaming updates
            
        Returns:
            Result of the tool execution
        """
        ...


class BaseTool(ABC):
    """
    Base implementation for tools with common functionality.
    
    This provides a foundation that concrete tools can build upon,
    similar to the BaseTool class in the original implementation.
    """
    
    def __init__(
        self,
        name: str,
        display_name: str,
        description: str,
        icon: Icon,
        is_output_markdown: bool = True,
        can_update_output: bool = False
    ):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.icon = icon
        self.is_output_markdown = is_output_markdown
        self.can_update_output = can_update_output
    
    def validate_params(self, params: Dict[str, Any]) -> Optional[str]:
        """
        Default parameter validation.
        
        Override this method in concrete tools for specific validation logic.
        """
        return None
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """
        Default description generator.
        
        Override this method in concrete tools for better descriptions.
        """
        return f"Execute {self.display_name} with parameters: {params}"
    
    def get_tool_locations(self, params: Dict[str, Any]) -> List[ToolLocation]:
        """
        Default implementation returns empty list.
        
        Override this method in tools that affect file system locations.
        """
        return []
    
    async def should_confirm_execute(
        self, 
        params: Dict[str, Any]
    ) -> Union[ToolConfirmationDetails, bool]:
        """
        Default implementation - no confirmation required.
        
        Override this method in tools that need user confirmation.
        """
        return False
    
    @abstractmethod
    async def execute(
        self, 
        params: Dict[str, Any],
        update_callback: Optional[callable] = None
    ) -> ToolResult:
        """
        Abstract method that concrete tools must implement.
        
        This is where the actual tool logic goes.
        """
        pass
    
    def create_result(
        self,
        content: str,
        display: Optional[str] = None,
        summary: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> ToolResult:
        """
        Helper method to create a ToolResult.
        
        Args:
            content: Content for LLM consumption
            display: Display content (defaults to content if not provided)
            summary: Optional summary
            success: Whether execution was successful
            error: Error message if failed
            
        Returns:
            ToolResult instance
        """
        return ToolResult(
            content=content,
            display=display or content,
            summary=summary,
            success=success,
            error=error
        )


class ReadOnlyTool(BaseTool):
    """
    Base class for read-only tools that don't modify the system.
    
    These tools typically don't require confirmation from the user.
    """
    
    def __init__(self, name: str, display_name: str, description: str, icon: Icon):
        super().__init__(name, display_name, description, icon)


class ModifyingTool(BaseTool):
    """
    Base class for tools that modify the file system or execute commands.
    
    These tools typically require user confirmation before execution.
    """
    
    def __init__(self, name: str, display_name: str, description: str, icon: Icon):
        super().__init__(name, display_name, description, icon)
    
    async def should_confirm_execute(
        self, 
        params: Dict[str, Any]
    ) -> Union[ToolConfirmationDetails, bool]:
        """
        Default confirmation for modifying tools.
        
        Override this method for custom confirmation logic.
        """
        locations = self.get_tool_locations(params)
        if locations:
            file_paths = [str(loc.path) for loc in locations]
            description = f"This will modify the following files: {', '.join(file_paths)}"
        else:
            description = f"This will execute: {self.get_description(params)}"
        
        return ToolConfirmationDetails(
            type="modify",
            title=f"Confirm {self.display_name}",
            description=description
        )