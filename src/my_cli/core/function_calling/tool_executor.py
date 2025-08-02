"""Tool executor for handling AI-requested tool executions with user confirmation."""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass
from datetime import datetime

from .function_parser import FunctionCallRequest
from ...tools.registry import ToolRegistry
from ...tools.scheduler import CoreToolScheduler, ToolCall
from ...tools.types import (
    ToolCallRequestInfo,
    ToolCallConfirmationDetails,
    ToolConfirmationOutcome,
    ToolResult
)

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    """Result of tool execution including confirmation flow."""
    function_call: FunctionCallRequest
    success: bool
    result: Optional[ToolResult] = None
    error: Optional[str] = None
    confirmation_outcome: Optional[ToolConfirmationOutcome] = None
    execution_time_ms: Optional[int] = None


class ToolExecutor:
    """Handles execution of AI-requested tool calls with user confirmation."""
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        config: Any,
        confirmation_handler: Optional[Callable[[ToolCallConfirmationDetails], ToolConfirmationOutcome]] = None,
        output_handler: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize tool executor.
        
        Args:
            tool_registry: Registry of available tools
            config: CLI configuration
            confirmation_handler: Handler for user confirmations
            output_handler: Handler for live output updates
        """
        self.tool_registry = tool_registry
        self.config = config
        self.confirmation_handler = confirmation_handler
        self.output_handler = output_handler
        
        # Create tool scheduler
        self.scheduler = CoreToolScheduler(
            tool_registry=dict(tool_registry._tools),
            config=config,
            output_update_handler=output_handler,
            on_all_tool_calls_complete=self._on_all_calls_complete,
            on_tool_calls_update=self._on_calls_update
        )
        
        self._execution_results: List[ToolExecutionResult] = []
        self._completion_event = asyncio.Event()
    
    async def execute_function_calls(
        self,
        function_calls: List[FunctionCallRequest],
        auto_confirm: bool = False
    ) -> List[ToolExecutionResult]:
        """
        Execute a list of function calls with confirmation workflow.
        
        Args:
            function_calls: List of function calls to execute
            auto_confirm: Whether to automatically confirm all tool executions
            
        Returns:
            List of execution results
        """
        if not function_calls:
            return []
        
        logger.info(f"Executing {len(function_calls)} function calls")
        
        # Reset state
        self._execution_results.clear()
        self._completion_event.clear()
        
        # Create initial execution results for all function calls
        for function_call in function_calls:
            result = ToolExecutionResult(
                function_call=function_call,
                success=False  # Will be updated on completion
            )
            self._execution_results.append(result)
        
        # Convert function calls to tool call requests
        tool_requests = [call.to_tool_call_request() for call in function_calls]
        
        try:
            # Temporarily set auto_confirm in config for this execution
            original_auto_confirm = getattr(self.config.settings, 'auto_confirm', False)
            if auto_confirm:
                self.config.settings.auto_confirm = True
            
            try:
                # Schedule tool executions
                await self.scheduler.schedule(tool_requests)
                
                # Handle confirmations for tools that need them (only if not auto_confirm)
                if not auto_confirm:
                    await self._handle_confirmations(function_calls, auto_confirm)
                
                # Wait for all executions to complete
                await self._completion_event.wait()
                
                return self._execution_results.copy()
                
            finally:
                # Restore original auto_confirm setting
                self.config.settings.auto_confirm = original_auto_confirm
        
        except Exception as e:
            logger.error(f"Error executing function calls: {e}")
            # Create error results for any remaining calls
            for call in function_calls:
                if not any(r.function_call.id == call.id for r in self._execution_results):
                    self._execution_results.append(ToolExecutionResult(
                        function_call=call,
                        success=False,
                        error=str(e)
                    ))
            return self._execution_results.copy()
    
    async def _handle_confirmations(
        self,
        function_calls: List[FunctionCallRequest],
        auto_confirm: bool
    ) -> None:
        """
        Handle confirmation workflow for tool executions.
        
        Args:
            function_calls: List of function calls being executed
            auto_confirm: Whether to auto-confirm all executions
        """
        # Get active tool calls that need confirmation
        active_calls = self.scheduler.get_active_calls()
        awaiting_approval = [
            call for call in active_calls
            if call.status.value == "awaiting_approval"
        ]
        
        for tool_call in awaiting_approval:
            try:
                if auto_confirm:
                    # Auto-confirm with proceed once
                    outcome = ToolConfirmationOutcome.PROCEED_ONCE
                else:
                    # Use confirmation handler if available
                    if self.confirmation_handler and tool_call.confirmation_details:
                        outcome = self.confirmation_handler(tool_call.confirmation_details)
                    else:
                        # Default to proceed once if no handler
                        outcome = ToolConfirmationOutcome.PROCEED_ONCE
                
                # Send confirmation to scheduler
                await self.scheduler.handle_confirmation(tool_call.request.call_id, outcome)
                
                # Record the outcome
                function_call = next(
                    (fc for fc in function_calls if fc.id == tool_call.request.call_id),
                    None
                )
                if function_call:
                    # Update or create result with confirmation outcome
                    existing_result = next(
                        (r for r in self._execution_results if r.function_call.id == function_call.id),
                        None
                    )
                    if existing_result:
                        existing_result.confirmation_outcome = outcome
                    else:
                        # Create result entry
                        self._execution_results.append(ToolExecutionResult(
                            function_call=function_call,
                            success=outcome != ToolConfirmationOutcome.CANCEL,
                            confirmation_outcome=outcome,
                            error="Cancelled by user" if outcome == ToolConfirmationOutcome.CANCEL else None
                        ))
            
            except Exception as e:
                logger.error(f"Error handling confirmation for {tool_call.request.call_id}: {e}")
    
    def _on_calls_update(self, tool_calls: List[ToolCall]) -> None:
        """Handle tool call status updates."""
        # This could be used for real-time UI updates
        pass
    
    def _on_all_calls_complete(self, completed_calls: List[ToolCall]) -> None:
        """
        Handle completion of all tool calls.
        
        Args:
            completed_calls: List of completed tool calls
        """
        logger.info(f"All {len(completed_calls)} tool calls completed")
        
        # Process results
        for tool_call in completed_calls:
            # Find corresponding function call
            function_call = None
            for result in self._execution_results:
                if result.function_call.id == tool_call.request.call_id:
                    function_call = result.function_call
                    break
            
            if not function_call:
                # This shouldn't happen, but handle gracefully
                continue
            
            # Find or create result
            result = next(
                (r for r in self._execution_results if r.function_call.id == function_call.id),
                None
            )
            
            if not result:
                result = ToolExecutionResult(
                    function_call=function_call,
                    success=False
                )
                self._execution_results.append(result)
            
            # Update result with execution outcome
            if tool_call.status.value == "success" and tool_call.response:
                # Extract tool result from response
                if hasattr(tool_call.response, 'result_display'):
                    # Create ToolResult from response
                    from ...tools.types import ToolResult
                    
                    # Extract content from response parts
                    content = ""
                    if hasattr(tool_call.response, 'response_parts'):
                        parts = tool_call.response.response_parts
                        if isinstance(parts, dict) and 'function_response' in parts:
                            func_response = parts['function_response']
                            if 'response' in func_response and 'output' in func_response['response']:
                                content = func_response['response']['output']
                    
                    # Get display string from ToolResultDisplay
                    display_str = str(tool_call.response.result_display)
                    
                    result.result = ToolResult(
                        llm_content=content,
                        return_display=display_str,
                        success=True
                    )
                    result.success = True
                else:
                    result.success = True
            
            elif tool_call.status.value in ["error", "cancelled"]:
                result.success = False
                if tool_call.response and tool_call.response.error:
                    result.error = str(tool_call.response.error)
                elif tool_call.status.value == "cancelled":
                    result.error = "Cancelled by user"
            
            # Record execution time
            if tool_call.duration_ms:
                result.execution_time_ms = tool_call.duration_ms
        
        # Signal completion
        self._completion_event.set()
    
    def get_execution_summary(self, results: List[ToolExecutionResult]) -> Dict[str, Any]:
        """
        Get summary of tool execution results.
        
        Args:
            results: List of execution results
            
        Returns:
            Summary dictionary
        """
        if not results:
            return {
                "total_calls": 0,
                "successful": 0,
                "failed": 0,
                "cancelled": 0,
                "total_time_ms": 0
            }
        
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        cancelled = sum(
            1 for r in results 
            if r.confirmation_outcome == ToolConfirmationOutcome.CANCEL
        )
        total_time = sum(r.execution_time_ms or 0 for r in results)
        
        return {
            "total_calls": len(results),
            "successful": successful,
            "failed": failed,
            "cancelled": cancelled,
            "total_time_ms": total_time,
            "average_time_ms": total_time / len(results) if results else 0
        }
