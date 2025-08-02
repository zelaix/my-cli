"""
Turn management system for My CLI conversations.

This module provides comprehensive turn management matching the original
Gemini CLI's conversation handling system.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

from pydantic import BaseModel, Field

from .streaming import (
    GeminiStreamEvent,
    StreamEvent,
    ContentStreamEvent,
    ToolCallRequestEvent,
    ToolCallResponseEvent,
    ErrorStreamEvent,
    FinishedStreamEvent,
    create_content_event,
    create_error_event,
    create_finished_event,
)
from .errors import GeminiError, classify_error

logger = logging.getLogger(__name__)


class TurnState(Enum):
    """States a turn can be in."""
    PENDING = "pending"
    RUNNING = "running"
    STREAMING = "streaming"
    WAITING_FOR_TOOL = "waiting_for_tool"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(Enum):
    """Message roles in a conversation."""
    USER = "user"
    MODEL = "model"
    TOOL = "tool"
    SYSTEM = "system"


class MessagePart(BaseModel):
    """A part of a message content."""
    text: Optional[str] = None
    function_call: Optional[Dict[str, Any]] = None
    function_response: Optional[Dict[str, Any]] = None
    inline_data: Optional[Dict[str, Any]] = None
    file_data: Optional[Dict[str, Any]] = None


class Message(BaseModel):
    """A message in a conversation."""
    role: MessageRole
    parts: List[MessagePart] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    
    @classmethod
    def create_text_message(cls, role: MessageRole, text: str) -> "Message":
        """Create a simple text message."""
        return cls(
            role=role,
            parts=[MessagePart(text=text)]
        )
    
    @classmethod
    def create_function_call_message(
        cls, 
        function_name: str, 
        function_args: Dict[str, Any]
    ) -> "Message":
        """Create a function call message."""
        return cls(
            role=MessageRole.MODEL,
            parts=[MessagePart(function_call={
                "name": function_name,
                "args": function_args
            })]
        )
    
    @classmethod
    def create_function_response_message(
        cls,
        function_name: str,
        response: Any
    ) -> "Message":
        """Create a function response message."""
        return cls(
            role=MessageRole.TOOL,
            parts=[MessagePart(function_response={
                "name": function_name,
                "response": response
            })]
        )
    
    def get_text_content(self) -> str:
        """Get all text content from the message."""
        text_parts = []
        for part in self.parts:
            if part.text:
                text_parts.append(part.text)
        return " ".join(text_parts)
    
    def has_function_calls(self) -> bool:
        """Check if message contains function calls."""
        return any(part.function_call for part in self.parts)
    
    def get_function_calls(self) -> List[Dict[str, Any]]:
        """Get all function calls from the message."""
        calls = []
        for part in self.parts:
            if part.function_call:
                calls.append(part.function_call)
        return calls


@dataclass
class TurnContext:
    """Context information for a turn."""
    prompt_id: str
    user_message: str
    model: str
    generation_config: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_config: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Turn:
    """
    Represents a single turn in a conversation.
    
    A turn encompasses the complete cycle from user input through model
    response, including any tool executions that may occur.
    """
    
    def __init__(
        self,
        turn_id: Optional[str] = None,
        context: Optional[TurnContext] = None
    ):
        self.id = turn_id or str(uuid.uuid4())
        self.context = context
        self.state = TurnState.PENDING
        self.messages: List[Message] = []
        self.events: List[GeminiStreamEvent] = []
        self.tool_executions: Dict[str, Any] = {}
        self.error: Optional[GeminiError] = None
        self.metadata: Dict[str, Any] = {}
        
        # Timing information
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # Statistics
        self.token_usage: Dict[str, int] = {}
        self.event_counts: Dict[str, int] = {}
        
        # Event handlers
        self._event_handlers: Dict[StreamEvent, List] = {}
        self._completion_callbacks: List = []
    
    def add_event_handler(self, event_type: StreamEvent, handler):
        """Add an event handler for this turn."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    def add_completion_callback(self, callback):
        """Add a callback to be called when the turn completes."""
        self._completion_callbacks.append(callback)
    
    async def emit_event(self, event: GeminiStreamEvent):
        """Emit an event for this turn."""
        self.events.append(event)
        
        # Update event counts
        event_name = event.type.value
        self.event_counts[event_name] = self.event_counts.get(event_name, 0) + 1
        
        # Call registered handlers
        if event.type in self._event_handlers:
            for handler in self._event_handlers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    logger.error(f"Error in turn event handler: {e}")
        
        # Handle state transitions
        await self._handle_event_state_transition(event)
    
    async def _handle_event_state_transition(self, event: GeminiStreamEvent):
        """Handle state transitions based on events."""
        if event.type == StreamEvent.CONTENT and self.state == TurnState.RUNNING:
            self.state = TurnState.STREAMING
        elif event.type == StreamEvent.TOOL_CALL_REQUEST and self.state in [TurnState.RUNNING, TurnState.STREAMING]:
            self.state = TurnState.WAITING_FOR_TOOL
        elif event.type == StreamEvent.FINISHED:
            await self._complete_turn(success=True)
        elif event.type == StreamEvent.ERROR:
            if hasattr(event.value, 'message'):
                self.error = classify_error(Exception(event.value.message))
            await self._complete_turn(success=False)
    
    async def start(self):
        """Start the turn execution."""
        if self.state != TurnState.PENDING:
            raise ValueError(f"Cannot start turn in state {self.state}")
        
        self.state = TurnState.RUNNING
        self.start_time = time.time()
        
        logger.info(f"Started turn {self.id}")
    
    async def _complete_turn(self, success: bool):
        """Complete the turn with success or failure."""
        if self.state in [TurnState.COMPLETED, TurnState.FAILED, TurnState.CANCELLED]:
            return  # Already completed
        
        self.end_time = time.time()
        self.state = TurnState.COMPLETED if success else TurnState.FAILED
        
        # Update metadata
        if self.start_time and self.end_time:
            self.metadata["duration_ms"] = (self.end_time - self.start_time) * 1000
        
        self.metadata["final_state"] = self.state.value
        self.metadata["event_counts"] = self.event_counts.copy()
        self.metadata["token_usage"] = self.token_usage.copy()
        
        # Call completion callbacks
        for callback in self._completion_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self)
                else:
                    callback(self)
            except Exception as e:
                logger.error(f"Error in completion callback: {e}")
        
        logger.info(f"Completed turn {self.id} in state {self.state.value}")
    
    async def cancel(self, reason: Optional[str] = None):
        """Cancel the turn."""
        if self.state in [TurnState.COMPLETED, TurnState.FAILED, TurnState.CANCELLED]:
            return  # Already completed
        
        self.state = TurnState.CANCELLED
        self.end_time = time.time()
        
        if reason:
            self.metadata["cancellation_reason"] = reason
        
        # Emit cancellation event
        from .streaming import UserCancelledEvent
        cancel_event = UserCancelledEvent(value=reason)
        await self.emit_event(cancel_event)
        
        logger.info(f"Cancelled turn {self.id}: {reason or 'No reason provided'}")
    
    def add_message(self, message: Message):
        """Add a message to this turn."""
        self.messages.append(message)
        
        # Update token usage if available
        if message.metadata and "token_count" in message.metadata:
            role_key = f"{message.role.value}_tokens"
            self.token_usage[role_key] = self.token_usage.get(role_key, 0) + message.metadata["token_count"]
    
    def get_messages_by_role(self, role: MessageRole) -> List[Message]:
        """Get all messages from a specific role."""
        return [msg for msg in self.messages if msg.role == role]
    
    def get_last_message(self, role: Optional[MessageRole] = None) -> Optional[Message]:
        """Get the last message, optionally filtered by role."""
        if role:
            role_messages = self.get_messages_by_role(role)
            return role_messages[-1] if role_messages else None
        return self.messages[-1] if self.messages else None
    
    def get_text_summary(self) -> str:
        """Get a text summary of the turn."""
        if not self.context:
            return f"Turn {self.id}: No context"
        
        user_msg = self.context.user_message[:100] + "..." if len(self.context.user_message) > 100 else self.context.user_message
        
        last_model_message = self.get_last_message(MessageRole.MODEL)
        model_response = ""
        if last_model_message:
            response_text = last_model_message.get_text_content()
            model_response = response_text[:100] + "..." if len(response_text) > 100 else response_text
        
        return f"Turn {self.id}: '{user_msg}' -> '{model_response}'"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert turn to dictionary representation."""
        return {
            "id": self.id,
            "state": self.state.value,
            "context": {
                "prompt_id": self.context.prompt_id if self.context else None,
                "user_message": self.context.user_message if self.context else None,
                "model": self.context.model if self.context else None,
            } if self.context else None,
            "messages": [
                {
                    "role": msg.role.value,
                    "parts": [part.dict() for part in msg.parts],
                    "metadata": msg.metadata
                } for msg in self.messages
            ],
            "event_counts": self.event_counts,
            "token_usage": self.token_usage,
            "metadata": self.metadata,
            "error": self.error.to_dict() if self.error else None,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get turn duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if turn is in a completed state."""
        return self.state in [TurnState.COMPLETED, TurnState.FAILED, TurnState.CANCELLED]
    
    @property
    def was_successful(self) -> bool:
        """Check if turn completed successfully."""
        return self.state == TurnState.COMPLETED


class TurnManager:
    """Manages multiple turns in a conversation."""
    
    def __init__(self, max_turns: int = 1000):
        self.max_turns = max_turns
        self.turns: List[Turn] = []
        self._active_turn: Optional[Turn] = None
        self._turn_history: Dict[str, Turn] = {}
    
    def create_turn(
        self,
        context: TurnContext,
        turn_id: Optional[str] = None
    ) -> Turn:
        """Create a new turn."""
        if len(self.turns) >= self.max_turns:
            # Remove oldest turns to make room
            old_turns = self.turns[:-self.max_turns + 1]
            for old_turn in old_turns:
                if old_turn.id in self._turn_history:
                    del self._turn_history[old_turn.id]
            self.turns = self.turns[-self.max_turns + 1:]
        
        turn = Turn(turn_id=turn_id, context=context)
        self.turns.append(turn)
        self._turn_history[turn.id] = turn
        
        return turn
    
    def get_turn(self, turn_id: str) -> Optional[Turn]:
        """Get a turn by ID."""
        return self._turn_history.get(turn_id)
    
    def get_active_turn(self) -> Optional[Turn]:
        """Get the currently active turn."""
        return self._active_turn
    
    def set_active_turn(self, turn: Turn):
        """Set the active turn."""
        self._active_turn = turn
    
    def get_recent_turns(self, count: int = 10) -> List[Turn]:
        """Get the most recent turns."""
        return self.turns[-count:] if count > 0 else self.turns
    
    def get_completed_turns(self) -> List[Turn]:
        """Get all completed turns."""
        return [turn for turn in self.turns if turn.is_completed]
    
    def get_conversation_history(
        self,
        include_system: bool = False,
        max_turns: Optional[int] = None
    ) -> List[Message]:
        """Get conversation history as a list of messages."""
        messages = []
        
        turns_to_include = self.turns
        if max_turns:
            turns_to_include = self.turns[-max_turns:]
        
        for turn in turns_to_include:
            for message in turn.messages:
                if not include_system and message.role == MessageRole.SYSTEM:
                    continue
                messages.append(message)
        
        return messages
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        completed_turns = self.get_completed_turns()
        successful_turns = [t for t in completed_turns if t.was_successful]
        
        total_tokens = {}
        total_events = {}
        total_duration = 0
        
        for turn in completed_turns:
            # Aggregate token usage
            for key, count in turn.token_usage.items():
                total_tokens[key] = total_tokens.get(key, 0) + count
            
            # Aggregate event counts
            for key, count in turn.event_counts.items():
                total_events[key] = total_events.get(key, 0) + count
            
            # Aggregate duration
            if turn.duration_ms:
                total_duration += turn.duration_ms
        
        return {
            "total_turns": len(self.turns),
            "completed_turns": len(completed_turns),
            "successful_turns": len(successful_turns),
            "success_rate": len(successful_turns) / len(completed_turns) if completed_turns else 0,
            "total_tokens": total_tokens,
            "total_events": total_events,
            "total_duration_ms": total_duration,
            "average_duration_ms": total_duration / len(completed_turns) if completed_turns else 0,
        }
    
    def clear_history(self, keep_recent: int = 0):
        """Clear conversation history, optionally keeping recent turns."""
        if keep_recent > 0:
            turns_to_keep = self.turns[-keep_recent:]
            turns_to_remove = self.turns[:-keep_recent]
        else:
            turns_to_keep = []
            turns_to_remove = self.turns
        
        # Remove from history dict
        for turn in turns_to_remove:
            if turn.id in self._turn_history:
                del self._turn_history[turn.id]
        
        self.turns = turns_to_keep
        
        # Clear active turn if it was removed
        if self._active_turn and self._active_turn not in turns_to_keep:
            self._active_turn = None


# Convenience functions

def create_turn_context(
    prompt_id: str,
    user_message: str,
    model: str,
    **kwargs
) -> TurnContext:
    """Create a turn context with the given parameters."""
    return TurnContext(
        prompt_id=prompt_id,
        user_message=user_message,
        model=model,
        **kwargs
    )


def create_simple_turn(
    user_message: str,
    model: str = "gemini-2.0-flash-exp",
    prompt_id: Optional[str] = None
) -> Turn:
    """Create a simple turn with basic context."""
    context = create_turn_context(
        prompt_id=prompt_id or str(uuid.uuid4()),
        user_message=user_message,
        model=model
    )
    return Turn(context=context)