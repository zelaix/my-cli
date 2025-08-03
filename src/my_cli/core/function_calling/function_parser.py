"""Parser for extracting function calls from AI responses."""

import json
import re
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime

from ...tools.types import ToolCallRequestInfo


@dataclass
class FunctionCallRequest:
    """Represents a function call request from AI."""
    id: str
    name: str
    arguments: Dict[str, Any]
    raw_arguments: str  # Original argument string from AI
    timestamp: datetime

    def to_tool_call_request(self) -> ToolCallRequestInfo:
        """Convert to ToolCallRequestInfo for execution."""
        return ToolCallRequestInfo(
            call_id=self.id,
            name=self.name,
            args=self.arguments,
            timestamp=self.timestamp
        )


def parse_function_calls(response_content: Any) -> List[FunctionCallRequest]:
    """
    Parse function calls from AI response content.
    
    Supports multiple formats:
    - Gemini native function calls (in candidates[0].content.parts)
    - Kimi/OpenAI-style tool_calls (in choices[0].message.tool_calls)
    - Legacy function_call format
    - Text-based function calls with special markers
    
    Args:
        response_content: AI response content (format varies by provider)
        
    Returns:
        List of parsed function call requests
    """
    function_calls = []
    
    # Handle Kimi/OpenAI response format first (choices-based)
    if hasattr(response_content, 'choices') and response_content.choices:
        # Object format - has choices attribute
        for choice in response_content.choices:
            if hasattr(choice, 'message') and choice.message:
                message = choice.message
                # Check for tool_calls in message
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tool_call in message.tool_calls:
                        call = _parse_openai_tool_call(tool_call)
                        if call:
                            function_calls.append(call)
    
    # Handle dictionary format with choices (Kimi response)
    elif isinstance(response_content, dict) and 'choices' in response_content:
        for choice in response_content['choices']:
            if isinstance(choice, dict) and 'message' in choice:
                message = choice['message']
                if isinstance(message, dict) and 'tool_calls' in message:
                    for tool_call in message['tool_calls']:
                        call = _parse_openai_tool_call(tool_call)
                        if call:
                            function_calls.append(call)
    
    # Handle Gemini native response format
    elif hasattr(response_content, 'candidates') and response_content.candidates:
        # Object format - has candidates attribute
        for candidate in response_content.candidates:
            if hasattr(candidate, 'content') and candidate.content:
                content = candidate.content
                # Check if content has parts (dictionary format)
                if isinstance(content, dict) and 'parts' in content:
                    for part in content['parts']:
                        if isinstance(part, dict) and 'function_call' in part:
                            call = _parse_gemini_function_call(part['function_call'])
                            if call:
                                function_calls.append(call)
                # Check if content has parts attribute (object format)
                elif hasattr(content, 'parts'):
                    for part in content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            call = _parse_gemini_function_call(part.function_call)
                            if call:
                                function_calls.append(call)
    
    # Handle dictionary format with candidates
    elif isinstance(response_content, dict) and 'candidates' in response_content:
        # Dictionary format - candidates is a key
        for candidate in response_content['candidates']:
            if isinstance(candidate, dict) and 'content' in candidate:
                content = candidate['content']
                if isinstance(content, dict) and 'parts' in content:
                    for part in content['parts']:
                        if isinstance(part, dict) and 'function_call' in part:
                            call = _parse_gemini_function_call(part['function_call'])
                            if call:
                                function_calls.append(call)
    
    # Handle direct parts format (from content generator)
    elif isinstance(response_content, dict) and 'parts' in response_content:
        for part in response_content['parts']:
            if isinstance(part, dict) and 'function_call' in part:
                call = _parse_gemini_function_call(part['function_call'])
                if call:
                    function_calls.append(call)
    
    # Handle legacy formats
    elif hasattr(response_content, 'function_call'):
        # Single function call (older format)
        call = _parse_single_function_call(response_content.function_call)
        if call:
            function_calls.append(call)
    
    elif hasattr(response_content, 'tool_calls'):
        # Multiple function calls (newer format)
        for tool_call in response_content.tool_calls:
            call = _parse_tool_call(tool_call)
            if call:
                function_calls.append(call)
    
    elif isinstance(response_content, dict):
        # Direct dictionary format
        if 'function_call' in response_content:
            call = _parse_single_function_call(response_content['function_call'])
            if call:
                function_calls.append(call)
        elif 'tool_calls' in response_content:
            for tool_call in response_content['tool_calls']:
                call = _parse_tool_call(tool_call)
                if call:
                    function_calls.append(call)
    
    elif isinstance(response_content, str):
        # Text-based function calls (for providers that return text)
        calls = _parse_text_function_calls(response_content)
        function_calls.extend(calls)
    
    return function_calls


def _parse_gemini_function_call(function_call: Any) -> Optional[FunctionCallRequest]:
    """
    Parse a Gemini native function call.
    
    Gemini function calls have this format:
    {
        "name": "function_name",
        "args": {"param1": "value1", "param2": "value2"}
    }
    """
    try:
        if isinstance(function_call, dict):
            name = function_call.get('name')
            args = function_call.get('args', {})
        elif hasattr(function_call, 'name') and hasattr(function_call, 'args'):
            name = function_call.name
            args = function_call.args
            # Convert protobuf args to Python dict if needed
            if hasattr(args, 'items'):
                # It's already a dict-like object
                args = dict(args.items()) if hasattr(args, 'items') else dict(args)
            elif hasattr(args, '__dict__'):
                # It's a protobuf message, convert to dict
                args = dict(args.__dict__)
        else:
            return None
        
        if not name:
            return None
        
        # Generate a unique call ID
        call_id = f"gemini_call_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(name) % 10000:04d}"
        
        return FunctionCallRequest(
            id=call_id,
            name=name,
            arguments=args,
            raw_arguments=str(args),
            timestamp=datetime.now()
        )
    
    except Exception:
        return None


def _parse_single_function_call(function_call: Any) -> Optional[FunctionCallRequest]:
    """Parse a single function call object."""
    try:
        if hasattr(function_call, 'name') and hasattr(function_call, 'arguments'):
            # Object with attributes
            name = function_call.name
            arguments_str = function_call.arguments
        elif isinstance(function_call, dict):
            # Dictionary format
            name = function_call.get('name')
            arguments_str = function_call.get('arguments', '{}')
        else:
            return None
        
        if not name:
            return None
        
        # Parse arguments JSON
        try:
            arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
        except json.JSONDecodeError:
            arguments = {}
        
        return FunctionCallRequest(
            id=f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(name) % 10000:04d}",
            name=name,
            arguments=arguments,
            raw_arguments=str(arguments_str),
            timestamp=datetime.now()
        )
    
    except Exception:
        return None


def _parse_openai_tool_call(tool_call: Any) -> Optional[FunctionCallRequest]:
    """
    Parse an OpenAI-style tool call (used by Kimi and other providers).
    
    OpenAI/Kimi tool calls have this format:
    {
        "id": "call_abc123",
        "type": "function",
        "function": {
            "name": "function_name",
            "arguments": '{"param1": "value1", "param2": "value2"}'
        }
    }
    """
    try:
        if hasattr(tool_call, 'id') and hasattr(tool_call, 'function'):
            # Object format
            call_id = tool_call.id
            function = tool_call.function
            name = function.name
            arguments_str = function.arguments
        elif isinstance(tool_call, dict):
            # Dictionary format
            call_id = tool_call.get('id', f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(tool_call)) % 10000:04d}")
            function = tool_call.get('function', {})
            name = function.get('name')
            arguments_str = function.get('arguments', '{}')
        else:
            return None
        
        if not name:
            return None
        
        # Parse arguments JSON string
        try:
            arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
        except json.JSONDecodeError:
            arguments = {}
        
        return FunctionCallRequest(
            id=call_id,
            name=name,
            arguments=arguments,
            raw_arguments=str(arguments_str),
            timestamp=datetime.now()
        )
    
    except Exception:
        return None


def _parse_tool_call(tool_call: Any) -> Optional[FunctionCallRequest]:
    """Parse a tool call object (legacy function, now delegates to OpenAI parser)."""
    return _parse_openai_tool_call(tool_call)


def _parse_text_function_calls(text: str) -> List[FunctionCallRequest]:
    """
    Parse function calls from text format (for providers that return text).
    
    Supports multiple patterns:
    1. Kimi K2 special markers:
       <|tool_calls_section_begin|>
       <|tool_call_begin|>{"name": "tool", "arguments": {...}}<|tool_call_end|>
       <|tool_calls_section_end|>
    
    2. XML-style function calls:
       <function_call name="tool_name">{"param": "value"}</function_call>
    
    3. Code block style:
       ```function_call
       name: tool_name
       arguments: {"param": "value"}
       ```
    """
    function_calls = []
    
    # Pattern 1: Kimi K2 special markers
    kimi_section_pattern = r'<\|tool_calls_section_begin\|>(.*?)<\|tool_calls_section_end\|>'
    kimi_call_pattern = r'<\|tool_call_begin\|>(.*?)<\|tool_call_end\|>'
    
    # Look for tool calls sections
    for section_match in re.finditer(kimi_section_pattern, text, re.DOTALL):
        section_content = section_match.group(1)
        
        # Parse individual tool calls within the section
        for call_match in re.finditer(kimi_call_pattern, section_content, re.DOTALL):
            call_content = call_match.group(1).strip()
            
            try:
                call_data = json.loads(call_content)
                name = call_data.get('name')
                arguments = call_data.get('arguments', {})
                
                if name:
                    function_calls.append(FunctionCallRequest(
                        id=f"kimi_call_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(function_calls):04d}",
                        name=name,
                        arguments=arguments,
                        raw_arguments=json.dumps(arguments),
                        timestamp=datetime.now()
                    ))
            except json.JSONDecodeError:
                continue
    
    # Pattern 2: XML-style function calls
    xml_pattern = r'<function_call\s+name="([^"]+)"\s*>([^<]*)</function_call>'
    for match in re.finditer(xml_pattern, text, re.DOTALL):
        name = match.group(1)
        arguments_str = match.group(2).strip()
        
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError:
            arguments = {}
        
        function_calls.append(FunctionCallRequest(
            id=f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(function_calls):04d}",
            name=name,
            arguments=arguments,
            raw_arguments=arguments_str,
            timestamp=datetime.now()
        ))
    
    # Pattern 3: Code block style function calls
    code_pattern = r'```function_call\s*\nname:\s*([^\n]+)\narguments:\s*([^`]*?)```'
    for match in re.finditer(code_pattern, text, re.DOTALL):
        name = match.group(1).strip()
        arguments_str = match.group(2).strip()
        
        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError:
            arguments = {}
        
        function_calls.append(FunctionCallRequest(
            id=f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(function_calls):04d}",
            name=name,
            arguments=arguments,
            raw_arguments=arguments_str,
            timestamp=datetime.now()
        ))
    
    return function_calls


def validate_function_call(call: FunctionCallRequest, available_tools: List[str]) -> bool:
    """
    Validate a function call request.
    
    Args:
        call: Function call to validate
        available_tools: List of available tool names
        
    Returns:
        True if call is valid
    """
    # Check if tool exists
    if call.name not in available_tools:
        return False
    
    # Check if arguments is a dictionary
    if not isinstance(call.arguments, dict):
        return False
    
    return True


def format_function_calls_for_display(calls: List[FunctionCallRequest]) -> str:
    """
    Format function calls for user display.
    
    Args:
        calls: List of function calls
        
    Returns:
        Formatted string for display
    """
    if not calls:
        return "No function calls found"
    
    lines = []
    for i, call in enumerate(calls, 1):
        lines.append(f"{i}. **{call.name}**")
        if call.arguments:
            formatted_args = json.dumps(call.arguments, indent=2)
            lines.append(f"   Arguments: ```json\n{formatted_args}\n```")
        else:
            lines.append("   Arguments: (none)")
        lines.append(f"   ID: `{call.id}`")
        lines.append("")
    
    return "\n".join(lines)
