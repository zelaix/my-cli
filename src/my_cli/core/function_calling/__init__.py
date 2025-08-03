"""Function calling integration for AI-Tool communication."""

from .schema_generator import generate_function_schema, generate_all_function_schemas
from .tool_executor import ToolExecutor, ToolExecutionResult
from .function_parser import parse_function_calls, FunctionCallRequest
from .result_processor import process_tool_result_for_ai
from .conversation_orchestrator import ConversationOrchestrator, ConversationTurn
from .confirmation_ui import ToolConfirmationUI, create_confirmation_handler

# New agentic components for multi-step tool calling
from .agentic_orchestrator import AgenticOrchestrator, StreamingEventProcessor
from .agentic_turn import AgenticTurn, AgenticTurnContext, AgenticTurnState
from .function_response_converter import (
    convert_to_function_response,
    format_tool_results_for_continuation,
    merge_function_response_parts
)

__all__ = [
    # Legacy components
    'generate_function_schema',
    'generate_all_function_schemas',
    'ToolExecutor',  
    'ToolExecutionResult',
    'parse_function_calls',
    'FunctionCallRequest',
    'process_tool_result_for_ai',
    'ConversationOrchestrator',
    'ConversationTurn',
    'ToolConfirmationUI',
    'create_confirmation_handler',
    
    # Agentic multi-step components
    'AgenticOrchestrator',
    'AgenticTurn',
    'AgenticTurnContext',
    'AgenticTurnState',
    'StreamingEventProcessor',
    'convert_to_function_response',
    'format_tool_results_for_continuation',
    'merge_function_response_parts',
]