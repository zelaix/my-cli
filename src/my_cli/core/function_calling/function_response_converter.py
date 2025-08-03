"""
Function response converter for multi-provider API compatibility.

This module provides proper conversion of tool results to both Gemini's
FunctionResponse format and Kimi/OpenAI tool response format.
"""

import logging
from typing import Any, Dict, List, Union

from ..client.turn import MessagePart
from ...tools.types import ToolResult

logger = logging.getLogger(__name__)


def create_function_response_part(
    call_id: str,
    tool_name: str,
    output: str,
    provider: str = "gemini"
) -> Dict[str, Any]:
    """
    Create a function response part for the specified provider.
    
    Args:
        call_id: Unique identifier for the tool call
        tool_name: Name of the tool
        output: Tool execution output
        provider: Provider format ('gemini' or 'kimi')
        
    Returns:
        Function response formatted for the provider
    """
    if provider.lower() == "kimi":
        # Kimi/OpenAI uses a different format for tool responses
        return {
            "role": "tool",
            "content": output,
            "tool_call_id": call_id,
            "name": tool_name
        }
    else:
        # Gemini format (default)
        return {
            "function_response": {
                "id": call_id,
                "name": tool_name,
                "response": {"output": output}
            }
        }


def create_gemini_function_response_part(
    call_id: str,
    tool_name: str,
    output: str
) -> Dict[str, Any]:
    """
    Create a function response part for Gemini API.
    
    Matches the original createFunctionResponsePart function.
    """
    return create_function_response_part(call_id, tool_name, output, "gemini")


def create_kimi_tool_response_message(
    call_id: str,
    tool_name: str,
    output: str
) -> Dict[str, Any]:
    """
    Create a tool response message for Kimi/OpenAI API.
    
    Kimi expects tool responses as separate messages with role='tool'.
    """
    return create_function_response_part(call_id, tool_name, output, "kimi")


def convert_to_function_response(
    tool_name: str,
    call_id: str,
    llm_content: Any,
    provider: str = "gemini"
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Convert tool result content to provider-specific function response format.
    
    This handles all the various content types that can be returned from tools
    and formats them appropriately for the specified provider.
    
    Args:
        tool_name: Name of the tool that was executed
        call_id: Unique identifier for the tool call
        llm_content: Content returned by the tool (various formats)
        provider: Provider format ('gemini' or 'kimi')
        
    Returns:
        Properly formatted function response for the specified provider
    """
    # Handle the content conversion logic from original
    content_to_process = llm_content
    
    # If it's a list with single item, unwrap it
    if isinstance(content_to_process, list) and len(content_to_process) == 1:
        content_to_process = content_to_process[0]
    
    # Handle string content (most common case)
    if isinstance(content_to_process, str):
        return create_function_response_part(call_id, tool_name, content_to_process, provider)
    
    # Handle list of content parts
    if isinstance(content_to_process, list):
        function_response = create_function_response_part(
            call_id,
            tool_name,
            "Tool execution succeeded.",
            provider
        )
        # Return function response plus the content parts
        return [function_response] + content_to_process
    
    # Handle dict content (single part object)
    if isinstance(content_to_process, dict):
        # If it's already a function response, handle appropriately
        if "function_response" in content_to_process:
            func_resp = content_to_process["function_response"]
            if "response" in func_resp and "content" in func_resp["response"]:
                # Extract text from nested content
                content_parts = func_resp["response"]["content"]
                if isinstance(content_parts, list):
                    text_content = ""
                    for part in content_parts:
                        if isinstance(part, dict) and "text" in part:
                            text_content += part["text"]
                    return create_function_response_part(call_id, tool_name, text_content, provider)
            # Pass through as-is if properly formatted
            return content_to_process
        
        # Handle inline data or file data
        if "inline_data" in content_to_process or "file_data" in content_to_process:
            mime_type = (
                content_to_process.get("inline_data", {}).get("mime_type") or
                content_to_process.get("file_data", {}).get("mime_type") or
                "unknown"
            )
            function_response = create_function_response_part(
                call_id,
                tool_name,
                f"Binary content of type {mime_type} was processed.",
                provider
            )
            return [function_response, content_to_process]
        
        # Handle text content in dict
        if "text" in content_to_process:
            return create_function_response_part(
                call_id, 
                tool_name, 
                content_to_process["text"],
                provider
            )
    
    # Handle ToolResult objects
    if isinstance(content_to_process, ToolResult):
        output_text = content_to_process.llm_content or "Tool execution succeeded."
        return create_function_response_part(call_id, tool_name, output_text, provider)
    
    # Default case for unknown content types
    return create_function_response_part(
        call_id,
        tool_name,
        "Tool execution succeeded.",
        provider
    )


def convert_tool_results_to_message_parts(
    tool_results: List[Dict[str, Any]]
) -> List[MessagePart]:
    """
    Convert completed tool results to message parts for conversation history.
    
    This processes tool execution results and formats them as function_response
    parts that can be added to the conversation history.
    
    Args:
        tool_results: List of completed tool execution results
        
    Returns:
        List of MessagePart objects with function_response content
    """
    message_parts = []
    
    for result in tool_results:
        if not hasattr(result, 'request') or not hasattr(result, 'response'):
            continue
        
        call_id = result.request.call_id
        tool_name = result.request.name
        
        # Extract the tool output
        output = "Tool execution completed."
        if hasattr(result.response, 'response_parts'):
            parts = result.response.response_parts
            if isinstance(parts, dict) and "function_response" in parts:
                func_resp = parts["function_response"]
                if "response" in func_resp and "output" in func_resp["response"]:
                    output = func_resp["response"]["output"]
        
        # Create function response part
        function_response = {
            "id": call_id,
            "name": tool_name,
            "response": {"output": output}
        }
        
        message_part = MessagePart(function_response=function_response)
        message_parts.append(message_part)
    
    return message_parts


def merge_function_response_parts(parts_list: List[Any]) -> List[Dict[str, Any]]:
    """
    Merge multiple function response parts into a single list.
    
    This handles the merging of tool responses that need to be sent
    back to the AI in a single continuation message.
    
    Args:
        parts_list: List of parts that may be dicts, lists, or other formats
        
    Returns:
        Flattened list of properly formatted parts
    """
    result_parts = []
    
    for item in parts_list:
        if isinstance(item, list):
            result_parts.extend(item)
        elif isinstance(item, dict):
            result_parts.append(item)
        elif hasattr(item, 'dict'):
            # Handle Pydantic models
            result_parts.append(item.dict())
        else:
            # Convert other types to dict if possible
            try:
                if hasattr(item, '__dict__'):
                    result_parts.append(item.__dict__)
                else:
                    logger.warning(f"Unknown part type in merge: {type(item)}")
            except Exception as e:
                logger.error(f"Error merging part: {e}")
    
    return result_parts


def format_tool_results_for_continuation(
    completed_tool_calls: List[Any]
) -> List[MessagePart]:
    """
    Format completed tool calls for automatic continuation.
    
    This is the key function that prepares tool results to be automatically
    fed back to the AI for continuation of the agentic loop.
    
    Args:
        completed_tool_calls: List of completed tool execution results
        
    Returns:
        List of MessagePart objects ready for AI continuation
    """
    message_parts = []
    
    for tool_call in completed_tool_calls:
        if not hasattr(tool_call, 'request') or not hasattr(tool_call, 'response'):
            continue
        
        # Skip cancelled tools unless we want to inform the AI
        if hasattr(tool_call, 'status') and tool_call.status.value == "cancelled":
            # Still include cancelled tools so AI knows what happened
            function_response = {
                "id": tool_call.request.call_id,
                "name": tool_call.request.name,
                "response": {"error": "Operation cancelled by user"}
            }
            message_parts.append(MessagePart(function_response=function_response))
            continue
        
        # Extract successful tool response
        if hasattr(tool_call.response, 'response_parts'):
            parts = tool_call.response.response_parts
            
            if isinstance(parts, dict) and "function_response" in parts:
                # Already properly formatted single response
                message_parts.append(MessagePart(function_response=parts["function_response"]))
            elif isinstance(parts, list):
                # Handle list of parts - find the function_response part only
                # (Lists from convertToFunctionResponse should have exactly one function_response part)
                function_response_part = None
                for part in parts:
                    if isinstance(part, dict) and "function_response" in part:
                        function_response_part = part["function_response"]
                        break
                
                if function_response_part:
                    message_parts.append(MessagePart(function_response=function_response_part))
            elif isinstance(parts, dict) and isinstance(parts.get("function_response"), dict):
                # Direct function response format
                message_parts.append(MessagePart(function_response=parts["function_response"]))
        
        # Fallback: create basic function response
        if not message_parts or message_parts[-1].function_response is None:
            basic_response = {
                "id": tool_call.request.call_id,
                "name": tool_call.request.name,
                "response": {"output": "Tool execution completed."}
            }
            message_parts.append(MessagePart(function_response=basic_response))
    
    return message_parts


def detect_provider_from_content_generator(content_generator) -> str:
    """
    Detect the provider from a content generator instance.
    
    Args:
        content_generator: Content generator instance
        
    Returns:
        Provider name ('gemini' or 'kimi')
    """
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


def convert_to_provider_response(
    tool_name: str,
    call_id: str,
    llm_content: Any,
    content_generator
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Convert tool result content to provider-specific format automatically.
    
    This is a convenience function that auto-detects the provider and
    formats the response appropriately.
    
    Args:
        tool_name: Name of the tool that was executed
        call_id: Unique identifier for the tool call
        llm_content: Content returned by the tool
        content_generator: Content generator instance to detect provider
        
    Returns:
        Properly formatted function response for the detected provider
    """
    provider = detect_provider_from_content_generator(content_generator)
    return convert_to_function_response(tool_name, call_id, llm_content, provider)


# Backward compatibility functions
def convert_to_gemini_function_response(
    tool_name: str,
    call_id: str,
    llm_content: Any
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Backward compatibility function for Gemini format."""
    return convert_to_function_response(tool_name, call_id, llm_content, "gemini")


def convert_to_kimi_tool_response(
    tool_name: str,
    call_id: str,
    llm_content: Any
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Convert tool result to Kimi/OpenAI tool response format."""
    return convert_to_function_response(tool_name, call_id, llm_content, "kimi")