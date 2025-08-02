"""Enhanced tool types and data structures for Phase 2.2 implementation."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime
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
    EDIT = "edit"
    WRITE = "write"
    READ = "read"


@dataclass
class ToolLocation:
    """Represents a file system location that a tool will affect."""
    path: str
    line: Optional[int] = None
    column: Optional[int] = None


class ToolConfirmationOutcome(Enum):
    """Outcomes for tool confirmation dialogs."""
    PROCEED_ONCE = "proceed_once"
    PROCEED_ALWAYS = "proceed_always" 
    PROCEED_ALWAYS_TOOL = "proceed_always_tool"
    MODIFY_WITH_EDITOR = "modify_with_editor"
    CANCEL = "cancel"


class ToolCallStatus(Enum):
    """Status of a tool call execution."""
    VALIDATING = "validating"
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"
    AWAITING_APPROVAL = "awaiting_approval"


@dataclass
class ToolCallConfirmationDetails:
    """Details for tool execution confirmation."""
    type: str  # "exec", "edit", "write", etc.
    title: str
    description: Optional[str] = None
    command: Optional[str] = None
    root_command: Optional[str] = None
    file_path: Optional[str] = None
    file_diff: Optional[str] = None
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    urls: Optional[List[str]] = None
    is_modifying: bool = False
    on_confirm: Optional[Callable[[ToolConfirmationOutcome], None]] = None


@dataclass
class ToolExecuteConfirmationDetails(ToolCallConfirmationDetails):
    """Specific confirmation details for shell execution."""
    pass

    def __post_init__(self):
        if not self.type:
            self.type = "exec"


@dataclass
class ToolEditConfirmationDetails(ToolCallConfirmationDetails):
    """Specific confirmation details for file editing."""
    file_name: Optional[str] = None
    
    def __post_init__(self):
        if not self.type:
            self.type = "edit"


class ToolResult(BaseModel):
    """Result of a tool execution."""
    
    llm_content: Union[str, List[Dict[str, Any]]] = Field(
        description="Content for LLM consumption - structured data or text"
    )
    
    return_display: Optional[str] = Field(
        default=None,
        description="User-friendly display content (markdown supported)"
    )
    
    success: bool = Field(
        default=True,
        description="Whether the tool execution was successful"
    )
    
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )


class ToolResultDisplay(BaseModel):
    """Display information for tool results."""
    file_diff: Optional[str] = None
    file_name: Optional[str] = None
    original_content: Optional[str] = None
    new_content: Optional[str] = None


@dataclass
class ToolCallRequestInfo:
    """Information about a tool call request."""
    call_id: str
    name: str
    args: Dict[str, Any]
    timestamp: datetime


@dataclass  
class ToolCallResponseInfo:
    """Information about a tool call response."""
    call_id: str
    response_parts: Any  # Function response parts for AI
    result_display: Optional[ToolResultDisplay] = None
    error: Optional[Exception] = None


ToolCallConfirmationPayload = Dict[str, Any]


P = TypeVar('P')  # Parameter type
R = TypeVar('R')  # Result type


class Tool(ABC, Generic[P, R]):
    """Enhanced abstract base class for all tools."""
    
    def __init__(
        self,
        name: str,
        display_name: str, 
        description: str,
        icon: Icon,
        schema: Dict[str, Any],
        is_output_markdown: bool = True,
        can_update_output: bool = False
    ):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.icon = icon
        self.schema = schema
        self.is_output_markdown = is_output_markdown
        self.can_update_output = can_update_output
    
    @abstractmethod
    def validate_tool_params(self, params: P) -> Optional[str]:
        """Validate tool parameters."""
        pass
    
    @abstractmethod
    def get_description(self, params: P) -> str:
        """Get description of what the tool will do."""
        pass
    
    def tool_locations(self, params: P) -> List[ToolLocation]:
        """Get locations that will be affected by this tool."""
        return []
    
    async def should_confirm_execute(
        self,
        params: P,
        abort_signal: asyncio.Event
    ) -> Union[ToolCallConfirmationDetails, bool]:
        """Check if tool execution needs confirmation."""
        return False
    
    @abstractmethod
    async def execute(
        self,
        params: P,
        abort_signal: asyncio.Event,
        update_callback: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """Execute the tool."""
        pass
