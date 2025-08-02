"""
Main Gemini client orchestrator for My CLI.

This module provides the comprehensive client that coordinates streaming,
authentication, conversation management, and tool execution, matching
the original Gemini CLI's architecture.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union, Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from .streaming import (
    GeminiStreamEvent,
    StreamEvent,
    StreamingManager,
    ContentStreamEvent,
    ToolCallRequestEvent,
    ToolCallResponseEvent,
    ErrorStreamEvent,
    FinishedStreamEvent,
    create_content_event,
    create_error_event,
    create_finished_event,
    create_tool_call_request_event,
    create_tool_call_response_event,
)
from .content_generator import (
    ContentGenerator,
    GeminiContentGenerator,
    ContentGeneratorConfig,
    AuthType,
    GenerateContentResponse,
)
from .turn import (
    Turn,
    TurnManager,
    TurnContext,
    TurnState,
    Message,
    MessageRole,
    create_turn_context,
)
from .errors import (
    GeminiError,
    AuthenticationError,
    ConfigurationError,
    classify_error,
    create_user_friendly_message,
)
from .retry import RetryManager, RetryConfig
from .token_manager import TokenManager, CompressionStrategy

logger = logging.getLogger(__name__)


@dataclass
class GeminiClientConfig:
    """Configuration for the main Gemini client."""
    # Content generation config
    content_generator_config: ContentGeneratorConfig
    
    # Conversation settings
    max_turns: int = 1000
    max_conversation_length: int = 100000  # tokens
    auto_compress_threshold: float = 0.8  # compress when 80% of limit reached
    
    # Tool execution
    enable_tools: bool = True
    tool_timeout_seconds: float = 30.0
    tool_confirmation_required: bool = False
    
    # Session management
    max_session_turns: int = 50
    session_timeout_minutes: int = 60
    detect_loops: bool = True
    loop_detection_threshold: int = 3
    
    # Retry and resilience
    retry_config: Optional[RetryConfig] = None
    enable_fallback: bool = True
    
    # Token management
    compression_strategy: CompressionStrategy = CompressionStrategy.SLIDING_WINDOW
    auto_compress_threshold: float = 0.8
    
    # Streaming
    stream_by_default: bool = True
    stream_timeout_seconds: float = 120.0


class ConversationSession(BaseModel):
    """Represents a conversation session."""
    session_id: str = Field(description="Unique session identifier")
    created_at: float = Field(description="Session creation timestamp")
    last_activity: float = Field(description="Last activity timestamp")
    turn_count: int = Field(default=0, description="Number of turns in session")
    token_count: int = Field(default=0, description="Estimated token count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session metadata")
    
    def is_expired(self, timeout_minutes: int) -> bool:
        """Check if session has expired."""
        current_time = time.time()
        return (current_time - self.last_activity) > (timeout_minutes * 60)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()


class GeminiClient:
    """
    Main Gemini client that orchestrates all aspects of AI interaction.
    
    This client provides a comprehensive interface for:
    - Content generation with multiple authentication methods
    - Streaming responses with event handling
    - Conversation management with turn tracking
    - Tool execution with confirmation workflows
    - Error handling and retry logic
    - Token management and compression
    """
    
    def __init__(self, config: GeminiClientConfig):
        self.config = config
        
        # Core components
        self.content_generator = GeminiContentGenerator(config.content_generator_config)
        self.streaming_manager = StreamingManager()
        self.turn_manager = TurnManager(max_turns=config.max_turns)
        self.retry_manager = RetryManager(config.retry_config or RetryConfig())
        self.token_manager = TokenManager(
            model=config.content_generator_config.model,
            compression_strategy=config.compression_strategy,
            auto_compress_threshold=config.auto_compress_threshold
        )
        
        # Session management
        self.current_session: Optional[ConversationSession] = None
        self.sessions: Dict[str, ConversationSession] = {}
        
        # Tool execution
        self.tool_executors: Dict[str, Callable] = {}
        self.pending_tool_calls: Dict[str, Dict[str, Any]] = {}
        
        # State
        self._initialized = False
        self._shutdown = False
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_tokens": 0,
            "total_duration_ms": 0,
        }
    
    async def initialize(self) -> None:
        """Initialize the client and all its components."""
        if self._initialized:
            return
        
        try:
            await self.content_generator.initialize()
            self._initialized = True
            
            logger.info("Gemini client initialized successfully")
            
        except Exception as e:
            error = classify_error(e)
            logger.error(f"Failed to initialize Gemini client: {error}")
            raise error
    
    async def shutdown(self) -> None:
        """Shutdown the client and cleanup resources."""
        self._shutdown = True
        
        # Cancel any pending operations
        active_turn = self.turn_manager.get_active_turn()
        if active_turn and not active_turn.is_completed:
            await active_turn.cancel("Client shutdown")
        
        # Clear handlers
        self.streaming_manager.clear_handlers()
        
        logger.info("Gemini client shutdown completed")
    
    def create_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationSession:
        """Create a new conversation session."""
        session_id = session_id or str(uuid.uuid4())
        session = ConversationSession(
            session_id=session_id,
            created_at=time.time(),
            last_activity=time.time(),
            metadata=metadata or {}
        )
        
        self.sessions[session_id] = session
        self.current_session = session
        
        logger.info(f"Created new session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get a session by ID."""
        return self.sessions.get(session_id)
    
    def set_current_session(self, session_id: str) -> bool:
        """Set the current active session."""
        session = self.get_session(session_id)
        if session:
            self.current_session = session
            return True
        return False
    
    async def send_message(
        self,
        message: str,
        *,
        stream: Optional[bool] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
        generation_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Union[GenerateContentResponse, AsyncGenerator[GeminiStreamEvent, None]]:
        """
        Send a message and get response.
        
        Args:
            message: The user message to send
            stream: Whether to stream the response (defaults to client config)
            model: Model to use (defaults to client config)
            session_id: Session ID to use (creates new if not provided)
            prompt_id: Unique prompt identifier
            generation_config: Additional generation parameters
            tools: Tools available for this request
            
        Returns:
            Either a complete response or an async generator of stream events
        """
        if not self._initialized:
            await self.initialize()
        
        if self._shutdown:
            raise GeminiError("Client has been shutdown")
        
        # Ensure we have a session
        if session_id:
            if not self.set_current_session(session_id):
                raise GeminiError(f"Session not found: {session_id}")
        elif not self.current_session:
            self.create_session()
        
        # Check session limits
        await self._check_session_limits()
        
        # Create turn context
        context = create_turn_context(
            prompt_id=prompt_id or str(uuid.uuid4()),
            user_message=message,
            model=model or self.config.content_generator_config.model,
            generation_config=generation_config,
            tools=tools,
        )
        
        # Create and start turn
        turn = self.turn_manager.create_turn(context)
        self.turn_manager.set_active_turn(turn)
        
        try:
            await turn.start()
            
            # Add user message to turn
            user_message = Message.create_text_message(MessageRole.USER, message)
            turn.add_message(user_message)
            
            # Update session
            self.current_session.turn_count += 1
            self.current_session.update_activity()
            
            # Decide whether to stream
            should_stream = stream if stream is not None else self.config.stream_by_default
            
            if should_stream:
                return self._send_message_stream(turn)
            else:
                return await self._send_message_sync(turn)
                
        except Exception as e:
            error = classify_error(e)
            await turn.emit_event(create_error_event(
                message=str(error),
                status=getattr(error, 'status', None),
                code=getattr(error, 'code', None)
            ))
            self.stats["failed_requests"] += 1
            raise error
    
    async def _send_message_sync(self, turn: Turn) -> GenerateContentResponse:
        """Send message and get synchronous response."""
        try:
            # Get conversation history
            history = self.turn_manager.get_conversation_history(max_turns=10)
            
            # Prepare messages with token management
            prepared_messages, prep_info = await self.token_manager.prepare_messages_for_generation(
                messages=history,
                max_output_tokens=self.config.content_generator_config.max_tokens,
                auto_compress=True
            )
            
            # Log compression if performed
            if prep_info.get("compression_performed"):
                logger.info(f"Conversation compressed: {prep_info['compression_info']}")
                # Could emit compression event here
            
            # Generate response
            response = await self.content_generator.generate_content(
                messages=prepared_messages,
                config=turn.context.generation_config
            )
            
            # Add model response to turn
            if response.has_content:
                model_message = Message.create_text_message(MessageRole.MODEL, response.text)
                turn.add_message(model_message)
            
            # Update statistics
            if response.usage_metadata:
                self.stats["total_tokens"] += response.usage_metadata.total_token_count
                self.current_session.token_count += response.usage_metadata.total_token_count
            
            self.stats["successful_requests"] += 1
            self.stats["total_requests"] += 1
            
            # Emit completion event
            await turn.emit_event(create_finished_event({
                "response_length": len(response.text),
                "token_usage": response.usage_metadata.dict() if response.usage_metadata else None
            }))
            
            return response
            
        except Exception as e:
            self.stats["failed_requests"] += 1
            self.stats["total_requests"] += 1
            raise classify_error(e)
    
    async def _send_message_stream(self, turn: Turn) -> AsyncGenerator[GeminiStreamEvent, None]:
        """Send message and get streaming response."""
        try:
            # Get conversation history
            history = self.turn_manager.get_conversation_history(max_turns=10)
            
            # Prepare messages with token management
            prepared_messages, prep_info = await self.token_manager.prepare_messages_for_generation(
                messages=history,
                max_output_tokens=self.config.content_generator_config.max_tokens,
                auto_compress=True
            )
            
            # Log compression if performed
            if prep_info.get("compression_performed"):
                logger.info(f"Conversation compressed: {prep_info['compression_info']}")
                # Could emit compression event here
            
            # Generate streaming response
            response_text = ""
            token_count = 0
            
            async for chunk in self.content_generator.generate_content_stream(
                messages=prepared_messages,
                config=turn.context.generation_config
            ):
                if chunk.has_content:
                    chunk_text = chunk.text
                    response_text += chunk_text
                    
                    # Create and emit content event
                    content_event = create_content_event(chunk_text)
                    await turn.emit_event(content_event)
                    yield content_event
                
                # Track token usage
                if chunk.usage_metadata:
                    token_count += chunk.usage_metadata.total_token_count
            
            # Add complete model response to turn
            if response_text:
                model_message = Message.create_text_message(MessageRole.MODEL, response_text)
                turn.add_message(model_message)
            
            # Update statistics
            self.stats["total_tokens"] += token_count
            self.current_session.token_count += token_count
            self.stats["successful_requests"] += 1
            self.stats["total_requests"] += 1
            
            # Emit completion event
            finished_event = create_finished_event({
                "response_length": len(response_text),
                "total_tokens": token_count
            })
            await turn.emit_event(finished_event)
            yield finished_event
            
        except Exception as e:
            self.stats["failed_requests"] += 1
            self.stats["total_requests"] += 1
            
            error = classify_error(e)
            error_event = create_error_event(
                message=str(error),
                status=getattr(error, 'status', None),
                code=getattr(error, 'code', None)
            )
            await turn.emit_event(error_event)
            yield error_event
    
    async def _check_session_limits(self) -> None:
        """Check and enforce session limits."""
        if not self.current_session:
            return
        
        # Check turn limit
        if self.current_session.turn_count >= self.config.max_session_turns:
            logger.warning(f"Session {self.current_session.session_id} reached max turns")
            # Could implement compression or session reset here
        
        # Check token limit
        if self.current_session.token_count >= self.config.max_conversation_length:
            if self.config.auto_compress_threshold:
                await self._compress_conversation()
        
        # Check expiration
        if self.current_session.is_expired(self.config.session_timeout_minutes):
            logger.info(f"Session {self.current_session.session_id} expired, creating new session")
            self.create_session()
    
    async def _compress_conversation(self) -> None:
        """Compress conversation history to reduce token usage."""
        logger.info("Compressing conversation history")
        
        # This is a placeholder for conversation compression logic
        # In a full implementation, this would:
        # 1. Identify turns that can be summarized
        # 2. Generate summaries of older conversations
        # 3. Replace detailed history with summaries
        # 4. Update token counts
        
        # For now, just clear older history
        self.turn_manager.clear_history(keep_recent=5)
        
        # Reset session token count (would be recalculated in full implementation)
        if self.current_session:
            self.current_session.token_count = 0
    
    def add_tool_executor(self, tool_name: str, executor: Callable) -> None:
        """Add a tool executor function."""
        self.tool_executors[tool_name] = executor
        logger.info(f"Added tool executor: {tool_name}")
    
    def remove_tool_executor(self, tool_name: str) -> bool:
        """Remove a tool executor."""
        if tool_name in self.tool_executors:
            del self.tool_executors[tool_name]
            logger.info(f"Removed tool executor: {tool_name}")
            return True
        return False
    
    def add_stream_handler(
        self,
        event_type: StreamEvent,
        handler: Callable[[GeminiStreamEvent], None]
    ) -> None:
        """Add a stream event handler."""
        self.streaming_manager.add_event_handler(event_type, handler)
    
    def add_global_stream_handler(
        self,
        handler: Callable[[GeminiStreamEvent], None]
    ) -> None:
        """Add a global stream event handler."""
        self.streaming_manager.add_global_handler(handler)
    
    def get_conversation_history(
        self,
        session_id: Optional[str] = None,
        max_turns: Optional[int] = None
    ) -> List[Message]:
        """Get conversation history for a session."""
        if session_id and session_id != (self.current_session.session_id if self.current_session else None):
            # Would need to implement session-specific history retrieval
            logger.warning(f"Cross-session history retrieval not implemented for {session_id}")
            return []
        
        return self.turn_manager.get_conversation_history(max_turns=max_turns)
    
    def get_session_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for a session or the current session."""
        session = None
        if session_id:
            session = self.get_session(session_id)
        else:
            session = self.current_session
        
        if not session:
            return {}
        
        turn_stats = self.turn_manager.get_statistics()
        
        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "turn_count": session.turn_count,
            "token_count": session.token_count,
            "duration_minutes": (time.time() - session.created_at) / 60,
            "turn_statistics": turn_stats,
            "metadata": session.metadata
        }
    
    def get_client_statistics(self) -> Dict[str, Any]:
        """Get overall client statistics."""
        return {
            "client_stats": self.stats.copy(),
            "active_sessions": len(self.sessions),
            "current_session": self.current_session.session_id if self.current_session else None,
            "total_turns": len(self.turn_manager.turns),
            "turn_statistics": self.turn_manager.get_statistics(),
            "token_statistics": self.token_manager.get_statistics(),
        }
    
    def count_tokens(self, content: Union[str, Message, List[Message]]) -> int:
        """Count tokens in various content types."""
        return self.token_manager.count_tokens(content)
    
    def get_token_limits(self) -> Dict[str, int]:
        """Get token limits for the current model."""
        limits = self.token_manager.get_token_limits()
        return {
            "input_tokens": limits.input_tokens,
            "output_tokens": limits.output_tokens,
            "total_tokens": limits.total_tokens,
        }


# Factory functions

def create_gemini_client_config(
    model: str = "gemini-2.0-flash-exp",
    auth_type: AuthType = AuthType.API_KEY,
    api_key: Optional[str] = None,
    max_tokens: int = 8192,
    temperature: float = 0.7,
    stream_by_default: bool = True,
    **kwargs
) -> GeminiClientConfig:
    """Create a Gemini client configuration."""
    content_config = ContentGeneratorConfig(
        model=model,
        auth_type=auth_type,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature
    )
    
    return GeminiClientConfig(
        content_generator_config=content_config,
        stream_by_default=stream_by_default,
        **kwargs
    )


def create_gemini_client(
    model: str = "gemini-2.0-flash-exp",
    auth_type: AuthType = AuthType.API_KEY,
    api_key: Optional[str] = None,
    max_tokens: int = 8192,
    temperature: float = 0.7,
    stream_by_default: bool = True,
    **kwargs
) -> GeminiClient:
    """Create a Gemini client with the given configuration."""
    config = create_gemini_client_config(
        model=model,
        auth_type=auth_type,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        stream_by_default=stream_by_default,
        **kwargs
    )
    return GeminiClient(config)