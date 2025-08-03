"""Orchestrator for managing AI-tool conversation flow."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator, Union
from dataclasses import dataclass

from .schema_generator import generate_all_function_schemas, format_tools_for_provider
from .gemini_schema_generator import generate_all_gemini_function_declarations
from .function_parser import parse_function_calls, FunctionCallRequest
from .tool_executor import ToolExecutor, ToolExecutionResult
from .result_processor import (
    process_all_tool_results_for_ai,
    create_execution_summary_for_user,
    extract_tool_outputs_for_display,
    should_continue_conversation
)
from ...tools.registry import ToolRegistry  
from ...tools.types import ToolConfirmationOutcome, ToolCallConfirmationDetails
from ..client.providers import BaseContentGenerator, GenerateContentResponse, GenerationCandidate, ModelProvider
from ..client.turn import Message, MessageRole, MessagePart
from ..prompts.system_prompt import get_core_system_prompt, load_workspace_context
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Represents a turn in the AI-tool conversation."""
    user_message: Optional[Message] = None
    ai_response: Optional[Any] = None
    function_calls: List[FunctionCallRequest] = None
    tool_results: List[ToolExecutionResult] = None
    final_ai_response: Optional[Any] = None
    
    def __post_init__(self):
        if self.function_calls is None:
            self.function_calls = []
        if self.tool_results is None:
            self.tool_results = []


class ConversationOrchestrator:
    """Orchestrates the flow between AI and tools in conversation."""
    
    def __init__(
        self,
        content_generator: BaseContentGenerator,
        tool_registry: ToolRegistry,
        config: Any,
        confirmation_handler: Optional[Callable[[ToolCallConfirmationDetails], ToolConfirmationOutcome]] = None,
        output_handler: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize conversation orchestrator.
        
        Args:
            content_generator: AI content generator
            tool_registry: Registry of available tools
            config: CLI configuration
            confirmation_handler: Handler for tool confirmations
            output_handler: Handler for output updates
        """
        self.content_generator = content_generator
        self.tool_registry = tool_registry
        self.config = config
        self.confirmation_handler = confirmation_handler
        self.output_handler = output_handler
        
        # Initialize tool executor
        self.tool_executor = ToolExecutor(
            tool_registry=tool_registry,
            config=config,
            confirmation_handler=confirmation_handler,
            output_handler=self._tool_output_handler
        )
        
        # Generate function schemas for AI (use native Gemini format)
        self.function_schemas = generate_all_gemini_function_declarations(tool_registry)
        # Convert to Gemini tools format for content generator
        from .gemini_schema_generator import format_tools_for_gemini_api
        self.gemini_tools = format_tools_for_gemini_api(self.function_schemas)
        
        # Store provider type for runtime decisions
        self.provider_type = content_generator.provider.value
        
        # Conversation history
        self.conversation_history: List[Message] = []
        self.conversation_turns: List[ConversationTurn] = []
        
        logger.info(f"Initialized orchestrator with {len(self.function_schemas)} tools")
    
    async def send_message(
        self,
        message: str,
        stream: bool = True,
        auto_confirm_tools: bool = False
    ) -> ConversationTurn:
        """
        Send a message to AI and handle any tool calls.
        
        Args:
            message: User message
            stream: Whether to use streaming responses
            auto_confirm_tools: Whether to auto-confirm tool executions
            
        Returns:
            Conversation turn with all interactions
        """
        turn = ConversationTurn()
        
        # Create user message
        user_message = Message(
            role=MessageRole.USER,
            parts=[MessagePart(text=message)]
        )
        turn.user_message = user_message
        
        # Add to conversation history
        self.conversation_history.append(user_message)
        
        try:
            # Prepare messages and system instruction
            messages, system_instruction = await self._prepare_messages_and_system_instruction(user_query=message)
            
            if stream:
                # Handle streaming response with tools
                turn = await self._handle_streaming_response(
                    messages, turn, auto_confirm_tools, system_instruction
                )
            else:
                # Handle non-streaming response with tools
                turn = await self._handle_non_streaming_response(
                    messages, turn, auto_confirm_tools, system_instruction
                )
            
            # Add turn to history
            self.conversation_turns.append(turn)
            
            return turn
        
        except Exception as e:
            logger.error(f"Error in conversation turn: {e}")
            # Create error turn
            turn.final_ai_response = f"Error: {str(e)}"
            return turn
    
    async def _handle_streaming_response(
        self,
        messages: List[Message],
        turn: ConversationTurn,
        auto_confirm_tools: bool,
        system_instruction: Optional[str] = None
    ) -> ConversationTurn:
        """Handle streaming AI response with tool calls."""
        response_text = ""
        response_chunks = []
        all_function_calls = []
        
        # Collect streaming response with tools available
        async for chunk in self.content_generator.generate_content_stream(
            messages, 
            tools=self.gemini_tools,
            system_instruction=system_instruction
        ):
            response_chunks.append(chunk)
            
            # Handle text content safely
            if chunk.has_content:
                try:
                    chunk_text = chunk.text
                    if chunk_text:
                        response_text += chunk_text
                        if self.output_handler:
                            self.output_handler(chunk_text)
                except Exception as e:
                    # If chunk contains function calls, chunk.text might fail
                    # This is expected and we'll handle function calls separately
                    logger.debug(f"Could not extract text from chunk: {e}")
            
            # Check for function calls in this chunk
            if chunk.tool_calls:
                chunk_function_calls = parse_function_calls(chunk)
                all_function_calls.extend(chunk_function_calls)
        
        # Process the complete response
        if response_chunks:
            # Create a combined response for processing
            combined_response = GenerateContentResponse(
                candidates=[
                    GenerationCandidate(
                        content={
                            "role": "model",
                            "parts": []
                        }
                    )
                ]
            )
            
            # Add text parts if we have text
            if response_text:
                combined_response.candidates[0].content["parts"].append({"text": response_text})
            
            # Add function call parts from all chunks
            for chunk in response_chunks:
                if chunk.candidates and chunk.candidates[0].content and "parts" in chunk.candidates[0].content:
                    for part in chunk.candidates[0].content["parts"]:
                        if isinstance(part, dict) and "function_call" in part:
                            combined_response.candidates[0].content["parts"].append(part)
            
            turn.ai_response = combined_response
            
            # Check for function calls in the complete response
            if all_function_calls:
                turn.function_calls = all_function_calls
                
                # Add the AI's response with function calls to conversation history
                function_call_parts = []
                for chunk in response_chunks:
                    if chunk.candidates and chunk.candidates[0].content and "parts" in chunk.candidates[0].content:
                        for part in chunk.candidates[0].content["parts"]:
                            if isinstance(part, dict) and "function_call" in part:
                                function_call_parts.append(MessagePart(function_call=part["function_call"]))
                
                if function_call_parts:
                    ai_message = Message(
                        role=MessageRole.MODEL,
                        parts=function_call_parts
                    )
                    self.conversation_history.append(ai_message)
                
                # Execute tools and continue conversation
                turn = await self._execute_tools_and_continue(
                    turn, auto_confirm_tools, stream=True, system_instruction=system_instruction
                )
            else:
                # No tools, just regular response
                if response_text:
                    ai_message = Message(
                        role=MessageRole.MODEL,
                        parts=[MessagePart(text=response_text)]
                    )
                    self.conversation_history.append(ai_message)
                    turn.final_ai_response = response_text
        
        return turn
    
    async def _handle_non_streaming_response(
        self,
        messages: List[Message],
        turn: ConversationTurn,
        auto_confirm_tools: bool,
        system_instruction: Optional[str] = None
    ) -> ConversationTurn:
        """Handle non-streaming AI response with tool calls."""
        response = await self.content_generator.generate_content(
            messages, 
            tools=self.gemini_tools,
            system_instruction=system_instruction
        )
        turn.ai_response = response
        
        # Check for function calls in response
        function_calls = parse_function_calls(response)
        
        if function_calls:
            turn.function_calls = function_calls
            
            # Add the AI's response with function calls to conversation history
            function_call_parts = []
            if response.candidates and response.candidates[0].content and "parts" in response.candidates[0].content:
                for part in response.candidates[0].content["parts"]:
                    if isinstance(part, dict) and "function_call" in part:
                        function_call_parts.append(MessagePart(function_call=part["function_call"]))
            
            if function_call_parts:
                ai_message = Message(
                    role=MessageRole.MODEL,
                    parts=function_call_parts
                )
                self.conversation_history.append(ai_message)
            
            # Execute tools and continue conversation
            turn = await self._execute_tools_and_continue(
                turn, auto_confirm_tools, stream=False, system_instruction=system_instruction
            )
        else:
            # No tools, just regular response
            ai_message = Message(
                role=MessageRole.MODEL,
                parts=[MessagePart(text=response.text)]
            )
            self.conversation_history.append(ai_message)
            turn.final_ai_response = response.text
        
        return turn
    
    async def _execute_tools_and_continue(
        self,
        turn: ConversationTurn,
        auto_confirm_tools: bool,
        stream: bool,
        system_instruction: Optional[str] = None
    ) -> ConversationTurn:
        """
        Execute tools and get AI's final response.
        
        Args:
            turn: Current conversation turn
            auto_confirm_tools: Whether to auto-confirm tools
            stream: Whether to use streaming for final response
            system_instruction: Optional system instruction for AI response
            
        Returns:
            Updated conversation turn
        """
        # Execute function calls
        if self.output_handler:
            self.output_handler("\n\n🔧 Executing tools...\n")
        
        execution_results = await self.tool_executor.execute_function_calls(
            turn.function_calls,
            auto_confirm=auto_confirm_tools
        )
        turn.tool_results = execution_results
        
        # Show tool execution summary to user
        if self.output_handler:
            summary = create_execution_summary_for_user(execution_results)
            self.output_handler(f"\n{summary}\n\n")
        
        # Add tool results to conversation history as a model message with function_response parts
        tool_result_message_data = process_all_tool_results_for_ai(execution_results)
        
        # Convert to our Message format
        message_parts = []
        for part in tool_result_message_data["parts"]:
            if "function_response" in part:
                # Create a MessagePart for function_response
                message_parts.append(MessagePart(function_response=part["function_response"]))
        
        if message_parts:
            tool_result_message = Message(
                role=MessageRole.MODEL,
                parts=message_parts
            )
            self.conversation_history.append(tool_result_message)
        
        # Check if we should continue conversation
        if should_continue_conversation(execution_results):
            # Get AI's response to tool results
            if self.output_handler:
                self.output_handler("🤖 AI is processing tool results...\n")
            
            messages_with_results = self.conversation_history.copy()
            
            try:
                if stream:
                    response_text = ""
                    async for chunk in self.content_generator.generate_content_stream(
                        messages_with_results, 
                        tools=self.gemini_tools,
                        system_instruction=system_instruction
                    ):
                        if chunk.has_content and chunk.text:
                            response_text += chunk.text
                            if self.output_handler:
                                self.output_handler(chunk.text)
                    
                    turn.final_ai_response = response_text
                    # Add final response to history
                    final_message = Message(
                        role=MessageRole.MODEL,
                        parts=[MessagePart(text=response_text)]
                    )
                    self.conversation_history.append(final_message)
                else:
                    response = await self.content_generator.generate_content(
                        messages_with_results, 
                        tools=self.gemini_tools,
                        system_instruction=system_instruction
                    )
                    turn.final_ai_response = response.text
                    # Add final response to history
                    final_message = Message(
                        role=MessageRole.MODEL,
                        parts=[MessagePart(text=response.text)]
                    )
                    self.conversation_history.append(final_message)
            
            except Exception as e:
                logger.error(f"Error getting AI response to tool results: {e}")
                turn.final_ai_response = f"Error processing tool results: {str(e)}"
        else:
            # Just show tool results without AI response
            outputs = extract_tool_outputs_for_display(execution_results)
            turn.final_ai_response = "\n\n".join(outputs) if outputs else "Tool execution completed."
        
        return turn
    
    async def _prepare_messages_and_system_instruction(self, user_query: Optional[str] = None) -> tuple[List[Message], Optional[str]]:
        """Prepare conversation messages and system instruction separately for Gemini's native support."""
        # Load workspace context
        workspace_context = load_workspace_context(Path.cwd())
        
        # Get available tool names
        available_tools = [tool.name for tool in self.tool_registry.get_all_tools()]
        
        # Generate system prompt/instruction
        system_instruction = get_core_system_prompt(
            workspace_context=workspace_context,
            available_tools=available_tools,
            user_query=user_query
        )
        
        # For Gemini, return messages without system prompt and system instruction separately
        if self.content_generator.provider == ModelProvider.GEMINI:
            return self.conversation_history.copy(), system_instruction
        else:
            # For other providers, include system prompt as USER message in conversation history
            system_message = Message(
                role=MessageRole.USER,  # Use USER role for compatibility
                parts=[MessagePart(text=system_instruction)]
            )
            messages = [system_message] + self.conversation_history.copy()
            return messages, None
    
    def _get_function_schemas_for_provider(self) -> Optional[List[Dict[str, Any]]]:
        """Get function schemas formatted for the current provider."""
        if not self.function_schemas:
            return None
            
        # For now, we use the native Gemini format for Gemini
        # and the same format for other providers (they'll need their own conversion)
        return self.function_schemas
    
    def _tool_output_handler(self, call_id: str, output: str) -> None:
        """Handle live tool output updates."""
        if self.output_handler:
            # Format tool output for display
            formatted_output = f"[{call_id[:8]}] {output}"
            self.output_handler(formatted_output)
    
    def get_conversation_history(self) -> List[Message]:
        """Get the current conversation history."""
        return self.conversation_history.copy()
    
    def clear_conversation_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()
        self.conversation_turns.clear()
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get conversation statistics."""
        total_turns = len(self.conversation_turns)
        turns_with_tools = sum(1 for turn in self.conversation_turns if turn.function_calls)
        total_tool_calls = sum(len(turn.function_calls) for turn in self.conversation_turns)
        successful_tools = sum(
            sum(1 for result in turn.tool_results if result.success)
            for turn in self.conversation_turns
        )
        
        return {
            "total_turns": total_turns,
            "turns_with_tools": turns_with_tools,
            "total_tool_calls": total_tool_calls,
            "successful_tool_calls": successful_tools,
            "available_tools": len(self.function_schemas)
        }
