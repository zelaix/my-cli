"""
Event-driven Turn Manager for agentic multi-step tool calling.

This module implements the same event-driven architecture as the original
Gemini CLI's Turn class, processing streaming responses and tool calls.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..client.providers import BaseContentGenerator, GenerateContentResponse
from ..client.turn import Message, MessageRole, MessagePart, TurnContext
from ..client.streaming import (
    GeminiStreamEvent,
    StreamEvent,
    ContentStreamEvent,
    ToolCallRequestEvent,
    ToolCallResponseEvent,
    ErrorStreamEvent,
    FinishedStreamEvent,
    ThoughtStreamEvent,
    UserCancelledEvent,
    ToolCallRequestInfo,
    ToolCallResponseInfo,
    ThoughtSummary,
    StructuredError,
    create_content_event,
    create_error_event,
    create_finished_event,
)
from ..client.errors import GeminiError, classify_error
from ...tools.registry import ToolRegistry
from ...tools.scheduler import CoreToolScheduler
from ...tools.types import ToolCallRequestInfo as ToolCallRequest

logger = logging.getLogger(__name__)


class AgenticTurnState(Enum):
    """States an agentic turn can be in."""
    PENDING = "pending"
    RUNNING = "running"
    STREAMING = "streaming"
    TOOL_EXECUTION = "tool_execution"
    WAITING_TOOL_CONFIRMATION = "waiting_tool_confirmation"
    PROCESSING_TOOL_RESULTS = "processing_tool_results"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgenticTurnContext:
    """Enhanced context for agentic turns."""
    prompt_id: str
    user_message: Union[str, List[MessagePart]]
    model: str
    content_generator: BaseContentGenerator
    tool_registry: Optional[ToolRegistry] = None
    tools: Optional[List[Dict[str, Any]]] = None
    system_instruction: Optional[str] = None
    generation_config: Optional[Dict[str, Any]] = None
    confirmation_handler: Optional[Callable] = None
    output_handler: Optional[Callable[[str], None]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgenticTurn:
    """
    Event-driven Turn Manager for multi-step agentic conversations.
    
    Processes streaming responses, handles tool calls, and manages
    conversation continuation automatically until completion.
    
    Matches the original Gemini CLI Turn.run() architecture.
    """
    
    def __init__(self, context: AgenticTurnContext):
        self.context = context
        self.id = str(uuid.uuid4())
        self.state = AgenticTurnState.PENDING
        
        # Conversation and event tracking
        self.conversation_history: List[Message] = []
        self.pending_tool_calls: List[ToolCallRequestInfo] = []
        self.debug_responses: List[GenerateContentResponse] = []
        self.events: List[GeminiStreamEvent] = []
        
        # State management
        self.finish_reason: Optional[str] = None
        self.error: Optional[GeminiError] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
        # Completion tracking (initialize before tool scheduler)
        self._completion_event = asyncio.Event()
        self._tool_completion_event = asyncio.Event()
        self._current_tool_results: List[Any] = []
        self._abort_signal = asyncio.Event()  # Abort signal for tool execution
        
        # Tool execution state
        self.tool_scheduler: Optional[CoreToolScheduler] = None
        if context.tool_registry:
            # Create a minimal config object for the scheduler
            from types import SimpleNamespace
            config = SimpleNamespace()
            config.settings = SimpleNamespace()
            config.settings.auto_confirm = False  # Require user confirmation for safety
            
            self.tool_scheduler = CoreToolScheduler(
                tool_registry=dict(context.tool_registry._tools),
                config=config,
                output_update_handler=self._handle_tool_output,
                on_all_tool_calls_complete=self._handle_tools_complete,
                on_tool_calls_update=self._handle_tool_calls_update
            )
            # Set the abort signal on the scheduler
            self.tool_scheduler._abort_signal = self._abort_signal
        
        logger.info(f"Created agentic turn {self.id}")
    
    async def run(
        self,
        initial_message: Union[str, List[MessagePart]],
        abort_signal: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[GeminiStreamEvent, None]:
        """
        Run the agentic turn with automatic tool execution and continuation.
        
        This is the main entry point that processes streaming responses,
        handles tool calls, and continues the conversation until completion.
        
        Args:
            initial_message: Initial user message or tool results
            abort_signal: Signal to abort the turn
            
        Yields:
            Stream events throughout the agentic conversation
        """
        try:
            await self._start_turn()
            
            # Convert message to proper format
            if isinstance(initial_message, str):
                message_parts = [MessagePart(text=initial_message)]
            else:
                message_parts = initial_message
            
            # Create initial message
            user_message = Message(
                role=MessageRole.USER,
                parts=message_parts
            )
            self.conversation_history.append(user_message)
            
            # Start the agentic loop
            async for event in self._agentic_loop(
                message_parts,
                abort_signal
            ):
                yield event
                
                # Check for abort
                if abort_signal and abort_signal.is_set():
                    await self._handle_user_cancellation()
                    return
        
        except Exception as e:
            logger.error(f"Error in agentic turn {self.id}: {e}")
            error_event = create_error_event(
                message=str(e),
                details={"turn_id": self.id}
            )
            await self._emit_event(error_event)
            yield error_event
            await self._complete_turn("failed")
    
    async def _agentic_loop(
        self,
        message_parts: List[MessagePart],
        abort_signal: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[GeminiStreamEvent, None]:
        """
        Core agentic loop that continues until AI provides final response.
        
        This implements the key pattern from the original Gemini CLI:
        1. Send message to AI
        2. Process streaming response
        3. If tool calls found, execute them
        4. Submit tool results back to AI (continuation)
        5. Repeat until AI gives final response without tools
        """
        current_message = message_parts
        is_continuation = False
        
        while True:
            # Check for abort
            if abort_signal and abort_signal.is_set():
                await self._handle_user_cancellation()
                return
            
            # Process AI response stream
            tool_calls_found = False
            
            try:
                async for event in self._process_ai_stream(
                    current_message,
                    is_continuation,
                    abort_signal
                ):
                    yield event
                    
                    # Track if we found tool calls
                    if event.type == StreamEvent.TOOL_CALL_REQUEST:
                        tool_calls_found = True
                    
                    # Check for completion
                    if event.type == StreamEvent.FINISHED:
                        if not tool_calls_found:
                            # AI finished without tools - end the loop
                            await self._complete_turn("completed")
                            return
                        else:
                            # AI finished but we have tools to execute
                            break
            
            except Exception as e:
                error_event = create_error_event(
                    message=f"Error in AI stream processing: {str(e)}",
                    details={"turn_id": self.id, "is_continuation": is_continuation}
                )
                await self._emit_event(error_event)
                yield error_event
                await self._complete_turn("failed")
                return
            
            # If we have tool calls, execute them and continue
            if tool_calls_found and self.pending_tool_calls:
                self.state = AgenticTurnState.TOOL_EXECUTION
                
                # CRITICAL FIX: Add the AI's response with function calls to conversation history
                # This ensures the conversation history has the MODEL message with function_call
                # before we add the USER message with function_response
                ai_response_parts = []
                        
                # Add function call parts (the critical missing piece)
                for tool_call in self.pending_tool_calls:
                    function_call_part = MessagePart(function_call={
                        "id": tool_call.call_id,
                        "name": tool_call.name,
                        "args": tool_call.args
                    })
                    ai_response_parts.append(function_call_part)
                
                # Add AI response to conversation history
                if ai_response_parts:  # Only add if we have parts
                    ai_response_message = Message(
                        role=MessageRole.MODEL,
                        parts=ai_response_parts
                    )
                    self.conversation_history.append(ai_response_message)
                
                # Execute tools and get results
                tool_result_parts = await self._execute_pending_tools(abort_signal)
                
                if not tool_result_parts:
                    # No valid tool results, end conversation
                    await self._complete_turn("completed")
                    return
                
                # Emit tool response events
                for part in tool_result_parts:
                    if hasattr(part, 'function_response'):
                        response_event = ToolCallResponseEvent(
                            value=ToolCallResponseInfo(
                                call_id=part.function_response.get('id', 'unknown'),
                                response_parts=[part.dict()],
                                result_display=None,
                                error=None
                            )
                        )
                        await self._emit_event(response_event)
                        yield response_event
                
                # Prepare for continuation with tool results
                current_message = tool_result_parts
                is_continuation = True
                
                # Add tool results to conversation history
                tool_result_message = Message(
                    role=MessageRole.USER,  # Tool results come from user role in Gemini
                    parts=tool_result_parts
                )
                self.conversation_history.append(tool_result_message)
                
                # Clear pending tool calls for next iteration
                self.pending_tool_calls.clear()
            else:
                # No tools to execute, conversation is complete
                await self._complete_turn("completed")
                return
    
    async def _process_ai_stream(
        self,
        message_parts: List[MessagePart],
        is_continuation: bool,
        abort_signal: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[GeminiStreamEvent, None]:
        """
        Process AI streaming response and extract events.
        
        This matches the original Turn.run() method's stream processing.
        """
        self.state = AgenticTurnState.STREAMING
        
        try:
            # Prepare messages for AI
            messages = self.conversation_history.copy()
            if not is_continuation:
                # For initial message, it's already in history
                pass
            else:
                # For continuation, the tool results are the latest message
                # They should already be in history from the agentic loop
                pass
            
            # Debug: Log messages being sent to API
            logger.info(f"🔍 API call debug (is_continuation={is_continuation}):")
            for i, msg in enumerate(messages):
                logger.info(f"  Message {i+1}: {msg.role.value}")
                for j, part in enumerate(msg.parts):
                    if part.text:
                        logger.info(f"    Part {j+1}: text = '{part.text[:50]}...'")
                    elif part.function_call:
                        logger.info(f"    Part {j+1}: function_call = {part.function_call}")
                    elif part.function_response:
                        fr = part.function_response
                        logger.info(f"    Part {j+1}: function_response id={fr.get('id')} name={fr.get('name')}")
            
            # For Kimi provider with tools, use non-streaming to avoid argument fragmentation
            # Streaming with Kimi fragments tool arguments across multiple chunks
            use_streaming = True
            if (hasattr(self.context.content_generator, 'provider') and 
                self.context.content_generator.provider.value == 'kimi' and 
                self.context.tools):
                use_streaming = False
            
            try:
                if use_streaming:
                    # Stream AI response
                    async for chunk in self.context.content_generator.generate_content_stream(
                        messages,
                        tools=self.context.tools,
                        system_instruction=self.context.system_instruction
                    ):
                        async for event in self._process_chunk(chunk, abort_signal, is_continuation):
                            yield event
                            if abort_signal and abort_signal.is_set():
                                return
                else:
                    # Use non-streaming for Kimi with tools to preserve arguments
                    response = await self.context.content_generator.generate_content(
                        messages,
                        tools=self.context.tools,
                        system_instruction=self.context.system_instruction
                    )
                    async for event in self._process_non_streaming_response(response, is_continuation):
                        yield event
            
            except Exception as e:
                logger.error(f"Error processing AI stream: {e}")
                error_event = create_error_event(
                    message=f"Stream processing error: {str(e)}",
                    details={"turn_id": self.id}
                )
                await self._emit_event(error_event)
                yield error_event
                raise
        
        except Exception as e:
            logger.error(f"Error processing AI stream: {e}")
            error_event = create_error_event(
                message=f"Stream processing error: {str(e)}",
                details={"turn_id": self.id}
            )
            await self._emit_event(error_event)
            yield error_event
            raise
    
    async def _process_chunk(self, chunk, abort_signal, is_continuation):
        """Process a streaming chunk."""
        # Check for abort
        if abort_signal and abort_signal.is_set():
            cancel_event = UserCancelledEvent(value="User aborted")
            await self._emit_event(cancel_event)
            yield cancel_event
            return
        
        # Store debug response
        self.debug_responses.append(chunk)
        
        # Process thought if present
        if hasattr(chunk, 'candidates') and chunk.candidates:
            candidate = chunk.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                parts = candidate.content.get('parts', [])
                for part in parts:
                    if isinstance(part, dict) and 'thought' in part:
                        thought_event = self._extract_thought_event(part)
                        if thought_event:
                            await self._emit_event(thought_event)
                            yield thought_event
                        continue
        
        # Process text content
        if chunk.has_content and chunk.text:
            content_event = create_content_event(chunk.text)
            await self._emit_event(content_event)
            yield content_event
            
            # Output to handler if available
            if self.context.output_handler:
                self.context.output_handler(chunk.text)
        
        # Process function calls (matching original Gemini CLI pattern) 
        if chunk.function_calls:
            for function_call in chunk.function_calls:
                event = self._handle_function_call(function_call)
                if event:
                    await self._emit_event(event)
                    yield event
        
        # Check for finish reason
        if hasattr(chunk, 'candidates') and chunk.candidates:
            candidate = chunk.candidates[0]
            if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                self.finish_reason = candidate.finish_reason
                finished_event = create_finished_event({
                    "finish_reason": candidate.finish_reason,
                    "is_continuation": is_continuation
                })
                await self._emit_event(finished_event)
                yield finished_event
                return
    
    async def _process_non_streaming_response(self, response, is_continuation):
        """Process a non-streaming response (used for Kimi with tools)."""
        # Store debug response
        self.debug_responses.append(response)
        
        # Process text content
        if response.has_content and response.text:
            content_event = create_content_event(response.text)
            await self._emit_event(content_event)
            yield content_event
            
            # Output to handler if available
            if self.context.output_handler:
                self.context.output_handler(response.text)
        
        # Process function calls
        if response.function_calls:
            for function_call in response.function_calls:
                event = self._handle_function_call(function_call)
                if event:
                    await self._emit_event(event)
                    yield event
        
        # Set finish reason from response
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                self.finish_reason = candidate.finish_reason
        
        # Always emit finished event for non-streaming
        finished_event = create_finished_event({
            "finish_reason": self.finish_reason or "stop",
            "is_continuation": is_continuation
        })
        await self._emit_event(finished_event)
        yield finished_event
    
    def _handle_function_call(self, tool_call: Dict[str, Any]) -> Optional[ToolCallRequestEvent]:
        """
        Handle function call from AI response.
        
        Matches the original handlePendingFunctionCall method.
        """
        # Use the exact ID from the function call (should match the one we preserved in function_calls property)
        call_id = tool_call.get('id')
        if not call_id:
            # Only generate if no ID exists (matching original Turn.ts pattern exactly)
            import time
            import random
            call_id = f"{tool_call.get('name', 'unknown')}-{int(time.time() * 1000)}-{hex(int(random.random() * 16**8))[2:]}"
        
        name = tool_call.get('name', 'undefined_tool_name')
        args = tool_call.get('args', {})
        
        tool_call_request = ToolCallRequestInfo(
            call_id=call_id,
            name=name,
            args=args,
            is_client_initiated=False,
            prompt_id=self.context.prompt_id
        )
        
        self.pending_tool_calls.append(tool_call_request)
        
        return ToolCallRequestEvent(value=tool_call_request)
    
    def _extract_thought_event(self, part: Dict[str, Any]) -> Optional[ThoughtStreamEvent]:
        """Extract thought event from AI response part."""
        if 'thought' not in part:
            return None
        
        thought_text = part.get('text', '')
        
        # Extract subject from **Subject** pattern
        import re
        subject_match = re.search(r'\*\*(.*?)\*\*', thought_text)
        subject = subject_match.group(1).strip() if subject_match else ''
        description = re.sub(r'\*\*(.*?)\*\*', '', thought_text).strip()
        
        thought = ThoughtSummary(
            subject=subject,
            description=description
        )
        
        return ThoughtStreamEvent(value=thought)
    
    async def _execute_pending_tools(
        self,
        abort_signal: Optional[asyncio.Event] = None
    ) -> List[MessagePart]:
        """
        Execute all pending tool calls and return results as message parts.
        
        This handles the tool execution phase of the agentic loop and implements
        the automatic feedback mechanism that enables multi-step tool calling.
        """
        if not self.pending_tool_calls or not self.tool_scheduler:
            return []
        
        self.state = AgenticTurnState.TOOL_EXECUTION
        
        # Convert to tool call requests for scheduler
        tool_requests = []
        for tool_call in self.pending_tool_calls:
            from datetime import datetime
            tool_request = ToolCallRequest(
                call_id=tool_call.call_id,
                name=tool_call.name,
                args=tool_call.args,
                timestamp=datetime.now()
            )
            tool_requests.append(tool_request)
        
        try:
            # Output tool execution start with detailed info
            if self.context.output_handler:
                if len(tool_requests) == 1:
                    req = tool_requests[0]
                    args_str = ", ".join(f"{k}={repr(v)}" for k, v in req.args.items()) if req.args else "no args"
                    self.context.output_handler(f"\n🔧 Executing tool: {req.name}({args_str})\n")
                else:
                    self.context.output_handler(f"\n🔧 Executing {len(tool_requests)} tools:\n")
                    for i, req in enumerate(tool_requests, 1):
                        args_str = ", ".join(f"{k}={repr(v)}" for k, v in req.args.items()) if req.args else "no args"
                        self.context.output_handler(f"  {i}. {req.name}({args_str})\n")
            
            # Schedule tool executions
            logger.info(f"Scheduling {len(tool_requests)} tool requests")
            for req in tool_requests:
                logger.info(f"  - Request: {req.name} (id: {req.call_id})")
            
            await self.tool_scheduler.schedule(tool_requests)
            
            # Check active calls after scheduling
            active_calls = self.tool_scheduler.get_active_calls()
            logger.info(f"Active calls after scheduling: {len(active_calls)}")
            for call in active_calls:
                logger.info(f"  - Active: {call.request.name} -> {call.status}")
            
            # Wait for completion
            logger.info("Waiting for tool completion...")
            await self._tool_completion_event.wait()
            logger.info("Tool completion event received")
            
            # Convert results to message parts using proper formatting
            from .function_response_converter import format_tool_results_for_continuation
            tool_result_parts = format_tool_results_for_continuation(self._current_tool_results)
            
            # Debug: check function call to function response matching
            logger.info(f"🔍 Function call/response matching debug:")
            logger.info(f"  - Pending tool calls: {len(self.pending_tool_calls)}")
            for i, call in enumerate(self.pending_tool_calls):
                logger.info(f"    {i+1}. {call.name} (id: {call.call_id})")
            logger.info(f"  - Tool result parts: {len(tool_result_parts)}")
            for i, part in enumerate(tool_result_parts):
                if part.function_response:
                    fr = part.function_response
                    logger.info(f"    {i+1}. {fr.get('name', '?')} (id: {fr.get('id', '?')})")
                else:
                    logger.info(f"    {i+1}. Non-function-response part: {type(part)}")
            
            # Output completion summary
            if self.context.output_handler:
                successful = sum(1 for r in self._current_tool_results if r.status.value == "success")
                total = len(self._current_tool_results)
                self.context.output_handler(f"✅ Completed {successful}/{total} tools successfully\n")
            
            return tool_result_parts
        
        except Exception as e:
            logger.error(f"Error executing tools: {e}")
            # Create error response parts
            error_parts = []
            for tool_call in self.pending_tool_calls:
                error_part = MessagePart(function_response={
                    "id": tool_call.call_id,
                    "name": tool_call.name,
                    "response": {"error": f"Tool execution failed: {str(e)}"}
                })
                error_parts.append(error_part)
            return error_parts
        finally:
            # Reset tool completion state
            self._tool_completion_event.clear()
            self._current_tool_results.clear()
    
    def _handle_tools_complete(self, completed_tools: List[Any]) -> None:
        """Handle completion of tool execution."""
        logger.info(f"🎉 CALLBACK TRIGGERED: Tools completed: {len(completed_tools)} tools")
        for i, tool in enumerate(completed_tools):
            logger.info(f"  Tool {i}: {tool.request.name} -> {tool.status}")
        self._current_tool_results = completed_tools
        logger.info("🔔 Setting completion event...")
        self._tool_completion_event.set()
        logger.info("✅ Completion event set!")
    
    def _handle_tool_calls_update(self, tool_calls: List[Any]) -> None:
        """Handle tool call status updates."""
        # Could be used for real-time UI updates
        pass
    
    def _handle_tool_output(self, call_id: str, output: str) -> None:
        """Handle live tool output."""
        if self.context.output_handler:
            formatted_output = f"[{call_id[:8]}] {output}"
            self.context.output_handler(formatted_output)
    
    async def _start_turn(self) -> None:
        """Start the turn execution."""
        if self.state != AgenticTurnState.PENDING:
            raise ValueError(f"Cannot start turn in state {self.state}")
        
        self.state = AgenticTurnState.RUNNING
        self.start_time = time.time()
        logger.info(f"Started agentic turn {self.id}")
    
    async def _complete_turn(self, final_state: str) -> None:
        """Complete the turn with the given state."""
        if self.state in [AgenticTurnState.COMPLETED, AgenticTurnState.FAILED, AgenticTurnState.CANCELLED]:
            return  # Already completed
        
        self.end_time = time.time()
        
        if final_state == "completed":
            self.state = AgenticTurnState.COMPLETED
        elif final_state == "failed":
            self.state = AgenticTurnState.FAILED
        elif final_state == "cancelled":
            self.state = AgenticTurnState.CANCELLED
        
        self._completion_event.set()
        logger.info(f"Completed agentic turn {self.id} in state {final_state}")
    
    async def _handle_user_cancellation(self) -> None:
        """Handle user cancellation of the turn."""
        await self._complete_turn("cancelled")
    
    async def _emit_event(self, event: GeminiStreamEvent) -> None:
        """Emit an event and track it."""
        self.events.append(event)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get turn duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
    
    @property
    def is_completed(self) -> bool:
        """Check if turn is completed."""
        return self.state in [
            AgenticTurnState.COMPLETED,
            AgenticTurnState.FAILED, 
            AgenticTurnState.CANCELLED
        ]
    
    def get_conversation_history(self) -> List[Message]:
        """Get the conversation history."""
        return self.conversation_history.copy()
    
    def get_debug_responses(self) -> List[GenerateContentResponse]:
        """Get debug responses for troubleshooting."""
        return self.debug_responses.copy()