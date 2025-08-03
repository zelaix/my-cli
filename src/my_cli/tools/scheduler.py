"""Tool execution scheduler with state management and confirmation workflows."""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Callable, Union, Any
from dataclasses import dataclass, field

from .types import (
    Tool,
    ToolCallStatus,
    ToolCallRequestInfo,
    ToolCallResponseInfo,
    ToolCallConfirmationDetails,
    ToolConfirmationOutcome,
    ToolResult,
    ToolResultDisplay
)
# Avoid circular import


@dataclass
class ToolCall:
    """Represents a tool call in various states of execution."""
    status: ToolCallStatus
    request: ToolCallRequestInfo
    tool: Optional[Tool] = None
    response: Optional[ToolCallResponseInfo] = None
    confirmation_details: Optional[ToolCallConfirmationDetails] = None
    start_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    outcome: Optional[ToolConfirmationOutcome] = None
    live_output: Optional[str] = None


ConfirmHandler = Callable[[ToolCall], ToolConfirmationOutcome]
OutputUpdateHandler = Callable[[str, str], None]  # (call_id, output_chunk)
AllToolCallsCompleteHandler = Callable[[List[ToolCall]], None]
ToolCallsUpdateHandler = Callable[[List[ToolCall]], None]


class CoreToolScheduler:
    """Manages tool execution with state tracking and confirmation workflows."""
    
    def __init__(
        self,
        tool_registry: Dict[str, Tool],
        config: Any,
        output_update_handler: Optional[OutputUpdateHandler] = None,
        on_all_tool_calls_complete: Optional[AllToolCallsCompleteHandler] = None,
        on_tool_calls_update: Optional[ToolCallsUpdateHandler] = None
    ):
        self.tool_registry = tool_registry
        self.config = config
        self.tool_calls: List[ToolCall] = []
        self.output_update_handler = output_update_handler
        self.on_all_tool_calls_complete = on_all_tool_calls_complete
        self.on_tool_calls_update = on_tool_calls_update
        self._abort_signal = asyncio.Event()
    
    def _create_error_response(
        self,
        request: ToolCallRequestInfo,
        error: Exception
    ) -> ToolCallResponseInfo:
        """Create an error response for a failed tool call."""
        return ToolCallResponseInfo(
            call_id=request.call_id,
            response_parts={
                "function_response": {
                    "id": request.call_id,
                    "name": request.name,
                    "response": {"error": str(error)}
                }
            },
            result_display=None,
            error=error
        )
    
    def _set_status(
        self,
        call_id: str,
        new_status: ToolCallStatus,
        **kwargs
    ) -> None:
        """Update the status of a tool call."""
        for i, call in enumerate(self.tool_calls):
            if call.request.call_id != call_id:
                continue
            
            # Don't change terminal states
            if call.status in [ToolCallStatus.SUCCESS, ToolCallStatus.ERROR, ToolCallStatus.CANCELLED]:
                continue
            
            # Calculate duration for terminal states
            duration_ms = None
            if call.start_time and new_status in [ToolCallStatus.SUCCESS, ToolCallStatus.ERROR, ToolCallStatus.CANCELLED]:
                duration_ms = int((datetime.now() - call.start_time).total_seconds() * 1000)
            
            # Update the tool call
            updated_call = ToolCall(
                status=new_status,
                request=call.request,
                tool=call.tool,
                response=kwargs.get('response', call.response),
                confirmation_details=kwargs.get('confirmation_details', call.confirmation_details),
                start_time=call.start_time,
                duration_ms=duration_ms or call.duration_ms,
                outcome=kwargs.get('outcome', call.outcome),
                live_output=kwargs.get('live_output', call.live_output)
            )
            
            self.tool_calls[i] = updated_call
            break
        
        self._notify_tool_calls_update()
        self._check_and_notify_completion()
    
    def _is_running(self) -> bool:
        """Check if any tool calls are currently running."""
        return any(
            call.status in [ToolCallStatus.EXECUTING, ToolCallStatus.AWAITING_APPROVAL]
            for call in self.tool_calls
        )
    
    async def schedule(
        self,
        requests: Union[ToolCallRequestInfo, List[ToolCallRequestInfo]]
    ) -> None:
        """Schedule tool calls for execution."""
        if self._is_running():
            raise RuntimeError(
                "Cannot schedule new tool calls while others are running"
            )
        
        request_list = requests if isinstance(requests, list) else [requests]
        
        # Create initial tool calls
        new_calls = []
        for request in request_list:
            tool = self.tool_registry.get(request.name)
            if not tool:
                # Create error call for unknown tool
                error_call = ToolCall(
                    status=ToolCallStatus.ERROR,
                    request=request,
                    response=self._create_error_response(
                        request,
                        ValueError(f"Tool '{request.name}' not found")
                    ),
                    start_time=datetime.now(),
                    duration_ms=0
                )
                new_calls.append(error_call)
            else:
                # Create validating call
                validating_call = ToolCall(
                    status=ToolCallStatus.VALIDATING,
                    request=request,
                    tool=tool,
                    start_time=datetime.now()
                )
                new_calls.append(validating_call)
        
        self.tool_calls.extend(new_calls)
        self._notify_tool_calls_update()
        
        # Process validation and confirmation for each call
        for call in new_calls:
            if call.status != ToolCallStatus.VALIDATING or not call.tool:
                continue
            
            try:
                # Validate parameters
                validation_error = call.tool.validate_tool_params(call.request.args)
                if validation_error:
                    self._set_status(
                        call.request.call_id,
                        ToolCallStatus.ERROR,
                        response=self._create_error_response(
                            call.request,
                            ValueError(validation_error)
                        )
                    )
                    continue
                
                # Check if confirmation is needed
                if getattr(self.config.settings, 'auto_confirm', False):
                    self._set_status(call.request.call_id, ToolCallStatus.SCHEDULED)
                else:
                    confirmation = await call.tool.should_confirm_execute(
                        call.request.args,
                        self._abort_signal
                    )
                    
                    if confirmation and isinstance(confirmation, ToolCallConfirmationDetails):
                        self._set_status(
                            call.request.call_id,
                            ToolCallStatus.AWAITING_APPROVAL,
                            confirmation_details=confirmation
                        )
                    else:
                        self._set_status(call.request.call_id, ToolCallStatus.SCHEDULED)
            
            except Exception as e:
                self._set_status(
                    call.request.call_id,
                    ToolCallStatus.ERROR,
                    response=self._create_error_response(call.request, e)
                )
        
        # Attempt to execute scheduled calls
        await self._execute_scheduled_calls()
    
    async def handle_confirmation(
        self,
        call_id: str,
        outcome: ToolConfirmationOutcome
    ) -> None:
        """Handle user confirmation response."""
        call = next(
            (c for c in self.tool_calls if c.request.call_id == call_id),
            None
        )
        
        if not call or call.status != ToolCallStatus.AWAITING_APPROVAL:
            return
        
        # Update outcome
        call.outcome = outcome
        
        if outcome == ToolConfirmationOutcome.CANCEL:
            # Create cancellation response
            cancel_response = ToolCallResponseInfo(
                call_id=call_id,
                response_parts={
                    "function_response": {
                        "id": call_id,
                        "name": call.request.name,
                        "response": {"error": "Operation cancelled by user"}
                    }
                },
                result_display=None,
                error=None
            )
            self._set_status(
                call_id,
                ToolCallStatus.CANCELLED,
                response=cancel_response,
                outcome=outcome
            )
        else:
            # Proceed with execution
            self._set_status(call_id, ToolCallStatus.SCHEDULED, outcome=outcome)
            await self._execute_scheduled_calls()
    
    async def _execute_scheduled_calls(self) -> None:
        """Execute all scheduled tool calls."""
        scheduled_calls = [
            call for call in self.tool_calls
            if call.status == ToolCallStatus.SCHEDULED
        ]
        
        # Execute calls concurrently
        if scheduled_calls:
            await asyncio.gather(
                *[self._execute_single_call(call) for call in scheduled_calls],
                return_exceptions=True
            )
    
    async def _execute_single_call(self, call: ToolCall) -> None:
        """Execute a single tool call."""
        if not call.tool:
            return
        
        self._set_status(call.request.call_id, ToolCallStatus.EXECUTING)
        
        try:
            # Set up live output callback if supported
            update_callback = None
            if call.tool.can_update_output and self.output_update_handler:
                def update_callback(output_chunk: str):
                    if self.output_update_handler:
                        self.output_update_handler(call.request.call_id, output_chunk)
                    # Update live output in call
                    for i, c in enumerate(self.tool_calls):
                        if c.request.call_id == call.request.call_id:
                            self.tool_calls[i].live_output = output_chunk
                            break
                    self._notify_tool_calls_update()
            
            # Execute the tool
            result = await call.tool.execute(
                call.request.args,
                self._abort_signal,
                update_callback
            )
            
            # Create success response using proper conversion (matching original Gemini CLI)
            from ..core.function_calling.function_response_converter import convert_to_function_response
            
            # Use the same pattern as original CoreToolScheduler.ts line 673-677
            converted_response = convert_to_function_response(
                call.request.name,  # toolName
                call.request.call_id,  # callId  
                result.llm_content  # toolResult.llmContent
            )
            
            response = ToolCallResponseInfo(
                call_id=call.request.call_id,
                response_parts=converted_response,
                result_display=ToolResultDisplay() if result.return_display else None,
                error=None
            )
            
            self._set_status(
                call.request.call_id,
                ToolCallStatus.SUCCESS,
                response=response
            )
        
        except Exception as e:
            self._set_status(
                call.request.call_id,
                ToolCallStatus.ERROR,
                response=self._create_error_response(call.request, e)
            )
    
    def _notify_tool_calls_update(self) -> None:
        """Notify listeners of tool call updates."""
        if self.on_tool_calls_update:
            self.on_tool_calls_update(self.tool_calls.copy())
    
    def _check_and_notify_completion(self) -> None:
        """Check if all calls are complete and notify if so."""
        if not self.tool_calls:
            return
        
        all_terminal = all(
            call.status in [ToolCallStatus.SUCCESS, ToolCallStatus.ERROR, ToolCallStatus.CANCELLED]
            for call in self.tool_calls
        )
        
        if all_terminal:
            completed_calls = self.tool_calls.copy()
            self.tool_calls.clear()
            
            if self.on_all_tool_calls_complete:
                self.on_all_tool_calls_complete(completed_calls)
    
    def get_active_calls(self) -> List[ToolCall]:
        """Get all currently active tool calls."""
        return self.tool_calls.copy()
    
    def abort_all(self) -> None:
        """Abort all running tool calls."""
        self._abort_signal.set()
        
        # Cancel all non-terminal calls
        for call in self.tool_calls:
            if call.status not in [ToolCallStatus.SUCCESS, ToolCallStatus.ERROR, ToolCallStatus.CANCELLED]:
                cancel_response = ToolCallResponseInfo(
                    call_id=call.request.call_id,
                    response_parts={
                        "function_response": {
                            "id": call.request.call_id,
                            "name": call.request.name,
                            "response": {"error": "Operation aborted by user"}
                        }
                    },
                    result_display=None,
                    error=None
                )
                self._set_status(
                    call.request.call_id,
                    ToolCallStatus.CANCELLED,
                    response=cancel_response
                )
