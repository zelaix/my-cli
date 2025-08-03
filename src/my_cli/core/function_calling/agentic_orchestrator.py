"""
Agentic Orchestrator for multi-step tool calling with automatic feedback loop.

This orchestrator implements the same automatic continuation pattern as the 
original Gemini CLI, where tool results are automatically fed back to the AI
to enable sophisticated multi-step reasoning and tool execution.
"""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Callable, Union

from .agentic_turn import AgenticTurn, AgenticTurnContext, AgenticTurnState
from .function_response_converter import (
    format_tool_results_for_continuation,
    convert_to_function_response,
    merge_function_response_parts
)
from ..client.providers import BaseContentGenerator
from ..client.turn import Message, MessageRole, MessagePart
from ..client.streaming import (
    GeminiStreamEvent,
    StreamEvent,
    ContentStreamEvent,
    ToolCallRequestEvent,
    ToolCallResponseEvent,
    ErrorStreamEvent,
    FinishedStreamEvent,
    create_content_event,
    create_error_event
)
from ...tools.registry import ToolRegistry
from ...tools.types import ToolCallConfirmationDetails, ToolConfirmationOutcome
from ..subagents import SimpleSubagentDelegator

logger = logging.getLogger(__name__)


class AgenticOrchestrator:
    """
    Multi-step agentic orchestrator with automatic tool feedback loop.
    
    This orchestrator implements the key pattern from the original Gemini CLI:
    1. Process AI streaming response
    2. Execute any requested tools
    3. Automatically feed tool results back to AI (continuation)
    4. Repeat until AI provides final response without tools
    
    This enables sophisticated multi-step reasoning and complex task execution.
    """
    
    def __init__(
        self,
        content_generator: BaseContentGenerator,
        tool_registry: ToolRegistry,
        config: Any,
        confirmation_handler: Optional[Callable[[ToolCallConfirmationDetails], ToolConfirmationOutcome]] = None,
        output_handler: Optional[Callable[[str], None]] = None
    ):
        self.content_generator = content_generator
        self.tool_registry = tool_registry
        self.config = config
        self.confirmation_handler = confirmation_handler
        self.output_handler = output_handler
        
        # Generate tools for AI - detect provider and use appropriate format
        self.provider = self._detect_provider(content_generator)
        
        if self.provider == "gemini":
            from .gemini_schema_generator import generate_all_gemini_function_declarations, format_tools_for_gemini_api
            self.function_schemas = generate_all_gemini_function_declarations(tool_registry)
            self.formatted_tools = format_tools_for_gemini_api(self.function_schemas)
        elif self.provider == "kimi":
            from .kimi_schema_generator import generate_all_kimi_function_schemas, format_tools_for_kimi_api
            self.function_schemas = generate_all_kimi_function_schemas(tool_registry)
            self.formatted_tools = format_tools_for_kimi_api(self.function_schemas)
        else:
            # Default to Gemini format for unknown providers
            from .gemini_schema_generator import generate_all_gemini_function_declarations, format_tools_for_gemini_api
            self.function_schemas = generate_all_gemini_function_declarations(tool_registry)
            self.formatted_tools = format_tools_for_gemini_api(self.function_schemas)
        
        # Conversation state
        self.conversation_history: List[Message] = []
        self.current_turn: Optional[AgenticTurn] = None
        
        # Statistics
        self.total_turns = 0
        self.total_tool_calls = 0
        self.successful_tool_calls = 0
        
        # Initialize subagent delegator for specialized task handling
        self.subagent_delegator = SimpleSubagentDelegator()
        
        logger.info(f"Initialized agentic orchestrator with {len(self.function_schemas)} tools for {self.provider} provider")
        logger.info(f"Subagent delegation enabled with {len(self.subagent_delegator.get_available_subagents())} specialists")
    
    def _detect_provider(self, content_generator) -> str:
        """Detect the provider from the content generator."""
        # Check if it's a Kimi generator
        if hasattr(content_generator, 'config') and hasattr(content_generator.config, 'kimi_provider'):
            return "kimi"
        
        # Check model name patterns
        if hasattr(content_generator, 'model'):
            model = content_generator.model.lower()
            if model.startswith('kimi-'):
                return "kimi"
            elif model.startswith('gemini-'):
                return "gemini"
        
        # Check config model
        if hasattr(content_generator, 'config') and hasattr(content_generator.config, 'model'):
            model = content_generator.config.model.lower()
            if model.startswith('kimi-'):
                return "kimi"
            elif model.startswith('gemini-'):
                return "gemini"
        
        # Default to gemini
        return "gemini"
    
    async def send_message(
        self,
        message: str,
        stream: bool = True,
        auto_confirm_tools: bool = False,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[GeminiStreamEvent, None]:
        """
        Send a message and handle the complete agentic conversation.
        
        This is the main entry point that starts the agentic loop and yields
        all events throughout the multi-step conversation.
        
        Args:
            message: User message to send
            stream: Whether to use streaming (always True for agentic behavior)
            auto_confirm_tools: Whether to auto-confirm tool executions
            system_instruction: Optional system instruction for AI
            
        Yields:
            All events throughout the agentic conversation
        """
        self.total_turns += 1
        
        # Check for subagent delegation first
        subagent = None
        if self.subagent_delegator.should_delegate(message):
            subagent = self.subagent_delegator.find_matching_subagent(message)
            if subagent and self.output_handler:
                self.output_handler(f"🤖 Using {subagent.name} specialist...\n\n")
        
        # Prepare system instruction (use subagent's prompt if delegated)
        if not system_instruction:
            if subagent:
                # Use subagent's specialized system prompt
                system_instruction = subagent.system_prompt
                logger.info(f"Using subagent '{subagent.name}' system prompt for task delegation")
            else:
                # Use default system instruction
                system_instruction = await self._prepare_system_instruction(message)
        
        # Create turn context with previous conversation history
        turn_context = AgenticTurnContext(
            prompt_id=f"turn-{self.total_turns}-{int(time.time())}",
            user_message=message,
            model=self.content_generator.model,
            content_generator=self.content_generator,
            tool_registry=self.tool_registry,
            tools=self.formatted_tools,
            system_instruction=system_instruction,
            confirmation_handler=self.confirmation_handler,
            output_handler=self.output_handler,
            previous_conversation_history=self.conversation_history.copy()
        )
        
        # Create and run agentic turn
        self.current_turn = AgenticTurn(turn_context)
        
        try:
            # Run the agentic turn and yield all events
            async for event in self.current_turn.run(message):
                yield event
                
                # Track statistics
                if event.type == StreamEvent.TOOL_CALL_REQUEST:
                    self.total_tool_calls += 1
                elif event.type == StreamEvent.TOOL_CALL_RESPONSE:
                    if not event.value.error:
                        self.successful_tool_calls += 1
            
            # Update conversation history from completed turn
            self.conversation_history.extend(self.current_turn.get_conversation_history())
            
        except Exception as e:
            logger.error(f"Error in agentic orchestrator: {e}")
            error_event = create_error_event(
                message=f"Orchestrator error: {str(e)}",
                details={"turn_id": self.current_turn.id if self.current_turn else "unknown"}
            )
            yield error_event
        
        finally:
            self.current_turn = None
    
    async def _prepare_system_instruction(self, user_query: str) -> str:
        """Prepare system instruction for the AI."""
        from ..prompts.system_prompt import get_core_system_prompt, load_workspace_context
        from pathlib import Path
        
        # Load workspace context
        workspace_context = load_workspace_context(Path.cwd())
        
        # Get available tool names
        available_tools = [tool.name for tool in self.tool_registry.get_all_tools()]
        
        # Generate system instruction
        return get_core_system_prompt(
            workspace_context=workspace_context,
            available_tools=available_tools,
            user_query=user_query
        )
    
    def get_conversation_history(self) -> List[Message]:
        """Get the complete conversation history."""
        return self.conversation_history.copy()
    
    def clear_conversation_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_history.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics including subagent information."""
        return {
            "total_turns": self.total_turns,
            "total_tool_calls": self.total_tool_calls,
            "successful_tool_calls": self.successful_tool_calls,
            "success_rate": (
                self.successful_tool_calls / self.total_tool_calls 
                if self.total_tool_calls > 0 else 0
            ),
            "available_tools": len(self.function_schemas),
            "current_turn_active": self.current_turn is not None,
            "subagents": {
                "available": [s.name for s in self.subagent_delegator.get_available_subagents()],
                "info": self.subagent_delegator.get_subagent_info()
            }
        }
    
    def get_subagent_info(self) -> Dict[str, str]:
        """Get information about available subagents."""
        return self.subagent_delegator.get_subagent_info()
    
    def test_subagent_delegation(self, test_tasks: List[str]) -> Dict[str, Optional[str]]:
        """Test subagent delegation for debugging purposes."""
        return self.subagent_delegator.test_task_patterns(test_tasks)


class StreamingEventProcessor:
    """
    Processes streaming events and manages tool execution state.
    
    This class handles the event-driven processing pattern from the original
    Gemini CLI, where streaming events are processed and tool calls are
    scheduled and executed based on the events received.
    """
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        confirmation_handler: Optional[Callable] = None,
        output_handler: Optional[Callable[[str], None]] = None
    ):
        self.tool_registry = tool_registry
        self.confirmation_handler = confirmation_handler
        self.output_handler = output_handler
        
        # Event tracking
        self.pending_tool_calls: List[Dict[str, Any]] = []
        self.completed_tool_calls: List[Dict[str, Any]] = []
        
        # State management
        self._tool_execution_complete = asyncio.Event()
    
    async def process_gemini_stream_events(
        self,
        stream: AsyncGenerator[GeminiStreamEvent, None],
        abort_signal: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[GeminiStreamEvent, None]:
        """
        Process streaming events and handle tool execution.
        
        This matches the original processGeminiStreamEvents pattern:
        1. Process content and thought events
        2. Collect tool call requests
        3. Execute tools when stream completes
        4. Return tool results for continuation
        
        Args:
            stream: Stream of events from AI
            abort_signal: Signal to abort processing
            
        Yields:
            Processed events including tool execution results
        """
        response_text = ""
        tool_call_requests = []
        
        # Process all streaming events
        async for event in stream:
            # Check for abort
            if abort_signal and abort_signal.is_set():
                return
            
            # Handle different event types
            if event.type == StreamEvent.CONTENT:
                response_text += event.value
                if self.output_handler:
                    self.output_handler(event.value)
                yield event
            
            elif event.type == StreamEvent.TOOL_CALL_REQUEST:
                tool_call_requests.append(event.value)
                yield event
            
            elif event.type == StreamEvent.FINISHED:
                yield event
                break
            
            else:
                # Pass through other events
                yield event
        
        # Execute tool calls if any were requested
        if tool_call_requests:
            async for tool_event in self._execute_tool_requests(
                tool_call_requests, 
                abort_signal
            ):
                yield tool_event
    
    async def _execute_tool_requests(
        self,
        tool_requests: List[Dict[str, Any]],
        abort_signal: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[GeminiStreamEvent, None]:
        """Execute tool requests and yield response events."""
        from ..function_calling.tool_executor import ToolExecutor
        from ..function_calling.function_parser import FunctionCallRequest
        
        # Convert to function call requests
        function_calls = []
        for request in tool_requests:
            func_call = FunctionCallRequest(
                id=request.call_id,
                name=request.name,
                args=request.args
            )
            function_calls.append(func_call)
        
        # Create tool executor
        executor = ToolExecutor(
            tool_registry=self.tool_registry,
            config=None,  # Will use default config
            confirmation_handler=self.confirmation_handler,
            output_handler=lambda call_id, output: (
                self.output_handler(f"[{call_id[:8]}] {output}")
                if self.output_handler else None
            )
        )
        
        # Execute tools
        results = await executor.execute_function_calls(
            function_calls,
            auto_confirm=False  # Use confirmation handler
        )
        
        # Yield tool response events
        for result in results:
            if result.success and result.result:
                # Convert result to proper format
                response_parts = convert_to_function_response(
                    result.function_call.name,
                    result.function_call.id,
                    result.result.llm_content
                )
                
                from ..client.streaming import ToolCallResponseInfo, ToolCallResponseEvent
                response_event = ToolCallResponseEvent(
                    value=ToolCallResponseInfo(
                        call_id=result.function_call.id,
                        response_parts=[response_parts] if isinstance(response_parts, dict) else response_parts,
                        result_display=None,
                        error=None
                    )
                )
                yield response_event
            else:
                # Error case
                from ..client.streaming import ToolCallResponseInfo, ToolCallResponseEvent
                error_response = ToolCallResponseEvent(
                    value=ToolCallResponseInfo(
                        call_id=result.function_call.id,
                        response_parts=[{
                            "function_response": {
                                "id": result.function_call.id,
                                "name": result.function_call.name,
                                "response": {"error": result.error or "Tool execution failed"}
                            }
                        }],
                        result_display=None,
                        error=result.error
                    )
                )
                yield error_response