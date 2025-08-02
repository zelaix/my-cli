"""
Event-driven streaming system for My CLI.

This module provides the streaming architecture that matches the original
Gemini CLI's event-driven approach for real-time AI interactions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import asyncio
import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StreamEvent(Enum):
    """Types of streaming events."""
    CONTENT = "content"
    TOOL_CALL_REQUEST = "tool_call_request"
    TOOL_CALL_RESPONSE = "tool_call_response"
    TOOL_CALL_CONFIRMATION = "tool_call_confirmation"
    USER_CANCELLED = "user_cancelled"
    ERROR = "error"
    CHAT_COMPRESSED = "chat_compressed"
    THOUGHT = "thought"
    MAX_SESSION_TURNS = "max_session_turns"
    FINISHED = "finished"
    LOOP_DETECTED = "loop_detected"


class GeminiStreamEvent(BaseModel):
    """Base class for all streaming events."""
    type: StreamEvent
    value: Optional[Any] = None
    
    class Config:
        arbitrary_types_allowed = True


class ContentStreamEvent(GeminiStreamEvent):
    """Event containing generated content."""
    type: StreamEvent = StreamEvent.CONTENT
    value: str = Field(description="Generated content text")


class ToolCallRequestInfo(BaseModel):
    """Information about a tool call request."""
    call_id: str = Field(description="Unique identifier for the tool call")
    name: str = Field(description="Name of the tool to call")
    args: Dict[str, Any] = Field(description="Arguments for the tool call")
    is_client_initiated: bool = Field(default=False, description="Whether call was initiated by client")
    prompt_id: str = Field(description="Prompt ID this tool call belongs to")


class ToolCallRequestEvent(GeminiStreamEvent):
    """Event containing a tool call request."""
    type: StreamEvent = StreamEvent.TOOL_CALL_REQUEST
    value: ToolCallRequestInfo


class ToolCallResponseInfo(BaseModel):
    """Information about a tool call response."""
    call_id: str = Field(description="Unique identifier matching the request")
    response_parts: List[Dict[str, Any]] = Field(description="Response content parts")
    result_display: Optional[Dict[str, Any]] = Field(default=None, description="Display information")
    error: Optional[str] = Field(default=None, description="Error message if call failed")


class ToolCallResponseEvent(GeminiStreamEvent):
    """Event containing a tool call response."""
    type: StreamEvent = StreamEvent.TOOL_CALL_RESPONSE
    value: ToolCallResponseInfo


class ToolCallConfirmationDetails(BaseModel):
    """Details about a tool call requiring confirmation."""
    request: ToolCallRequestInfo
    details: Dict[str, Any] = Field(description="Additional confirmation details")


class ToolCallConfirmationEvent(GeminiStreamEvent):
    """Event requesting confirmation for a tool call."""
    type: StreamEvent = StreamEvent.TOOL_CALL_CONFIRMATION
    value: ToolCallConfirmationDetails


class StructuredError(BaseModel):
    """Structured error information."""
    message: str = Field(description="Error message")
    status: Optional[int] = Field(default=None, description="HTTP status code if applicable")
    code: Optional[str] = Field(default=None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")


class ErrorStreamEvent(GeminiStreamEvent):
    """Event containing error information."""
    type: StreamEvent = StreamEvent.ERROR
    value: StructuredError


class ThoughtSummary(BaseModel):
    """Summary of AI thinking process."""
    subject: str = Field(description="Subject of the thought")
    description: str = Field(description="Description of the thinking process")


class ThoughtStreamEvent(GeminiStreamEvent):
    """Event containing AI thought process."""
    type: StreamEvent = StreamEvent.THOUGHT
    value: ThoughtSummary


class ChatCompressionInfo(BaseModel):
    """Information about chat compression."""
    original_token_count: int = Field(description="Token count before compression")
    new_token_count: int = Field(description="Token count after compression")
    compression_ratio: float = Field(description="Compression ratio (new/original)")


class ChatCompressedEvent(GeminiStreamEvent):
    """Event indicating chat history was compressed."""
    type: StreamEvent = StreamEvent.CHAT_COMPRESSED
    value: ChatCompressionInfo


class FinishedStreamEvent(GeminiStreamEvent):
    """Event indicating streaming has finished."""
    type: StreamEvent = StreamEvent.FINISHED
    value: Optional[Dict[str, Any]] = Field(default=None, description="Final metadata")


class MaxSessionTurnsEvent(GeminiStreamEvent):
    """Event indicating maximum session turns reached."""
    type: StreamEvent = StreamEvent.MAX_SESSION_TURNS
    value: Optional[Dict[str, Any]] = Field(default=None, description="Session metadata")


class LoopDetectedEvent(GeminiStreamEvent):
    """Event indicating a conversation loop was detected."""
    type: StreamEvent = StreamEvent.LOOP_DETECTED
    value: Optional[Dict[str, Any]] = Field(default=None, description="Loop detection metadata")


class UserCancelledEvent(GeminiStreamEvent):
    """Event indicating user cancelled the operation."""
    type: StreamEvent = StreamEvent.USER_CANCELLED
    value: Optional[str] = Field(default=None, description="Cancellation reason")


class StreamingManager:
    """Manages streaming events and their processing."""
    
    def __init__(self):
        self._event_handlers: Dict[StreamEvent, List] = {}
        self._global_handlers: List = []
    
    def add_event_handler(self, event_type: StreamEvent, handler):
        """Add an event handler for a specific event type."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def add_global_handler(self, handler):
        """Add a global event handler that receives all events."""
        self._global_handlers.append(handler)
    
    async def emit_event(self, event: GeminiStreamEvent):
        """Emit an event to all registered handlers."""
        # Call global handlers
        for handler in self._global_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {e}")
        
        # Call specific event handlers
        if event.type in self._event_handlers:
            for handler in self._event_handlers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Error in {event.type} event handler: {e}")
    
    def remove_event_handler(self, event_type: StreamEvent, handler):
        """Remove a specific event handler."""
        if event_type in self._event_handlers:
            try:
                self._event_handlers[event_type].remove(handler)
            except ValueError:
                pass
    
    def remove_global_handler(self, handler):
        """Remove a global event handler."""
        try:
            self._global_handlers.remove(handler)
        except ValueError:
            pass
    
    def clear_handlers(self):
        """Clear all event handlers."""
        self._event_handlers.clear()
        self._global_handlers.clear()


def create_content_event(content: str) -> ContentStreamEvent:
    """Create a content streaming event."""
    return ContentStreamEvent(value=content)


def create_error_event(
    message: str,
    status: Optional[int] = None,
    code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> ErrorStreamEvent:
    """Create an error streaming event."""
    error = StructuredError(
        message=message,
        status=status,
        code=code,
        details=details
    )
    return ErrorStreamEvent(value=error)


def create_finished_event(metadata: Optional[Dict[str, Any]] = None) -> FinishedStreamEvent:
    """Create a finished streaming event."""
    return FinishedStreamEvent(value=metadata)


def create_tool_call_request_event(
    call_id: str,
    name: str,
    args: Dict[str, Any],
    prompt_id: str,
    is_client_initiated: bool = False
) -> ToolCallRequestEvent:
    """Create a tool call request event."""
    request_info = ToolCallRequestInfo(
        call_id=call_id,
        name=name,
        args=args,
        prompt_id=prompt_id,
        is_client_initiated=is_client_initiated
    )
    return ToolCallRequestEvent(value=request_info)


def create_tool_call_response_event(
    call_id: str,
    response_parts: List[Dict[str, Any]],
    result_display: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> ToolCallResponseEvent:
    """Create a tool call response event."""
    response_info = ToolCallResponseInfo(
        call_id=call_id,
        response_parts=response_parts,
        result_display=result_display,
        error=error
    )
    return ToolCallResponseEvent(value=response_info)


# Event type mapping for easier access
EVENT_CLASSES = {
    StreamEvent.CONTENT: ContentStreamEvent,
    StreamEvent.TOOL_CALL_REQUEST: ToolCallRequestEvent,
    StreamEvent.TOOL_CALL_RESPONSE: ToolCallResponseEvent,
    StreamEvent.TOOL_CALL_CONFIRMATION: ToolCallConfirmationEvent,
    StreamEvent.ERROR: ErrorStreamEvent,
    StreamEvent.THOUGHT: ThoughtStreamEvent,
    StreamEvent.CHAT_COMPRESSED: ChatCompressedEvent,
    StreamEvent.FINISHED: FinishedStreamEvent,
    StreamEvent.MAX_SESSION_TURNS: MaxSessionTurnsEvent,
    StreamEvent.LOOP_DETECTED: LoopDetectedEvent,
    StreamEvent.USER_CANCELLED: UserCancelledEvent,
}