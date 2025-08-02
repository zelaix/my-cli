"""Process tool execution results for AI conversation context."""

import json
from typing import List, Dict, Any, Union
from datetime import datetime

from .tool_executor import ToolExecutionResult
from ...tools.types import ToolResult


def process_tool_result_for_ai(
    execution_result: ToolExecutionResult
) -> Dict[str, Any]:
    """
    Process a single tool execution result for AI consumption.
    
    Args:
        execution_result: Tool execution result
        
    Returns:
        Processed result as a function_response part for Gemini
    """
    call = execution_result.function_call
    
    if execution_result.success and execution_result.result:
        # Successful execution
        content = execution_result.result.llm_content
        if isinstance(content, list):
            # Convert list to string if needed
            content = json.dumps(content, ensure_ascii=False)
        
        # Return as Gemini function_response format with matching ID
        return {
            "function_response": {
                "id": call.id,  # Include the original call ID
                "name": call.name,
                "response": {"output": str(content)}
            }
        }
    else:
        # Failed execution
        error_msg = execution_result.error or "Tool execution failed"
        
        # Return as Gemini function_response format with error
        return {
            "function_response": {
                "id": call.id,  # Include the original call ID
                "name": call.name,
                "response": {"error": error_msg}
            }
        }


def process_all_tool_results_for_ai(
    execution_results: List[ToolExecutionResult]
) -> Dict[str, Any]:
    """
    Process multiple tool execution results for AI consumption.
    
    Creates a single "model" role message with function_response parts
    as expected by Gemini's native function calling.
    
    Args:
        execution_results: List of tool execution results
        
    Returns:
        Model message with function_response parts for Gemini
    """
    # Convert all results to function_response parts
    function_response_parts = [
        process_tool_result_for_ai(result)
        for result in execution_results
    ]
    
    # Return as a "model" role message with function_response parts
    return {
        "role": "model", 
        "parts": function_response_parts
    }


def create_function_response_parts(
    execution_results: List[ToolExecutionResult]
) -> List[Dict[str, Any]]:
    """
    Create function response parts for AI conversation.
    
    Args:
        execution_results: List of tool execution results
        
    Returns:
        List of function response parts
    """
    response_parts = []
    
    for result in execution_results:
        call = result.function_call
        
        if result.success and result.result:
            # Successful execution
            content = result.result.llm_content
            if isinstance(content, list):
                content = json.dumps(content, ensure_ascii=False)
            
            response_parts.append({
                "functionResponse": {
                    "id": call.id,
                    "name": call.name,
                    "response": {
                        "output": str(content)
                    }
                }
            })
        else:
            # Failed execution
            error_msg = result.error or "Tool execution failed"
            
            response_parts.append({
                "functionResponse": {
                    "id": call.id,
                    "name": call.name,
                    "response": {
                        "error": error_msg
                    }
                }
            })
    
    return response_parts


def create_execution_summary_for_user(
    execution_results: List[ToolExecutionResult]
) -> str:
    """
    Create a user-friendly summary of tool executions.
    
    Args:
        execution_results: List of tool execution results
        
    Returns:
        Formatted summary string
    """
    if not execution_results:
        return "No tools were executed."
    
    lines = []
    successful = 0
    failed = 0
    
    for i, result in enumerate(execution_results, 1):
        call = result.function_call
        
        if result.success:
            successful += 1
            status_icon = "✅"
            status_text = "Success"
        else:
            failed += 1
            status_icon = "❌"
            status_text = f"Failed: {result.error or 'Unknown error'}"
        
        # Format execution time
        time_str = ""
        if result.execution_time_ms is not None:
            if result.execution_time_ms < 1000:
                time_str = f" ({result.execution_time_ms}ms)"
            else:
                time_str = f" ({result.execution_time_ms / 1000:.1f}s)"
        
        lines.append(f"{i}. {status_icon} **{call.name}** - {status_text}{time_str}")
        
        # Show result preview if available
        if result.success and result.result and result.result.return_display:
            preview = result.result.return_display
            if len(preview) > 100:
                preview = preview[:97] + "..."
            lines.append(f"   {preview}")
    
    # Add summary header
    total = len(execution_results)
    header = f"**Tool Execution Summary**: {successful}/{total} successful"
    if failed > 0:
        header += f", {failed} failed"
    
    return header + "\n\n" + "\n".join(lines)


def extract_tool_outputs_for_display(
    execution_results: List[ToolExecutionResult]
) -> List[str]:
    """
    Extract tool outputs for display to user.
    
    Args:
        execution_results: List of tool execution results
        
    Returns:
        List of display strings
    """
    outputs = []
    
    for result in execution_results:
        if result.success and result.result and result.result.return_display:
            outputs.append(result.result.return_display)
        elif not result.success:
            error_msg = result.error or "Tool execution failed"
            outputs.append(f"**Error in {result.function_call.name}**: {error_msg}")
    
    return outputs


def format_tool_calls_for_conversation(
    execution_results: List[ToolExecutionResult]
) -> str:
    """
    Format tool execution results for inclusion in conversation context.
    
    Args:
        execution_results: List of tool execution results
        
    Returns:
        Formatted string for conversation
    """
    if not execution_results:
        return ""
    
    sections = []
    
    for result in execution_results:
        call = result.function_call
        
        # Tool call header
        sections.append(f"## Tool: {call.name}")
        
        # Arguments
        if call.arguments:
            args_str = json.dumps(call.arguments, indent=2, ensure_ascii=False)
            sections.append(f"**Arguments:**\n```json\n{args_str}\n```")
        
        # Result
        if result.success and result.result:
            if result.result.return_display:
                sections.append(f"**Result:**\n{result.result.return_display}")
            elif result.result.llm_content:
                content = result.result.llm_content
                if isinstance(content, list):
                    content = json.dumps(content, indent=2, ensure_ascii=False)
                sections.append(f"**Result:**\n```\n{content}\n```")
        else:
            error_msg = result.error or "Tool execution failed"
            sections.append(f"**Error:** {error_msg}")
        
        sections.append("")  # Empty line
    
    return "\n".join(sections)


def should_continue_conversation(
    execution_results: List[ToolExecutionResult]
) -> bool:
    """
    Determine if conversation should continue based on tool results.
    
    Args:
        execution_results: List of tool execution results
        
    Returns:
        True if conversation should continue with AI response
    """
    # Continue if we have successful tool executions
    return any(result.success for result in execution_results)
