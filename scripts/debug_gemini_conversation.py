#!/usr/bin/env python3
"""Debug script to test Gemini native function calling step by step."""

import asyncio
import json
import os
import logging
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(level=logging.DEBUG)

from src.my_cli.core.client.content_generator import GeminiContentGenerator, GeminiProviderConfig
from src.my_cli.core.client.turn import Message, MessageRole, MessagePart
from src.my_cli.core.function_calling.gemini_schema_generator import generate_all_gemini_function_declarations
from src.my_cli.tools.registry import ToolRegistry

async def test_gemini_conversation():
    """Test the complete Gemini conversation flow with function calling."""
    
    # Initialize tool registry
    tool_registry = ToolRegistry()
    await tool_registry.discover_builtin_tools(None)  # Discover builtin tools
    
    # Generate function schemas
    function_schemas = generate_all_gemini_function_declarations(tool_registry)
    print(f"Generated {len(function_schemas)} function schemas")
    
    # Initialize Gemini content generator
    from src.my_cli.core.client.providers import ModelProvider, AuthType
    gemini_config = GeminiProviderConfig(
        provider=ModelProvider.GEMINI,
        auth_type=AuthType.API_KEY,
        model="gemini-2.0-flash-exp",
        api_key=os.getenv("GOOGLE_API_KEY")
    )
    
    content_generator = GeminiContentGenerator(gemini_config)
    await content_generator.initialize()
    
    # Create user message
    user_message = Message(
        role=MessageRole.USER,
        parts=[MessagePart(text="list the current directory")]
    )
    
    print("\n=== Step 1: Initial request ===")
    print(f"User message: {user_message.dict()}")
    
    # Get AI response with tools
    messages = [user_message]
    response = await content_generator.generate_content(messages, tools=function_schemas)
    
    print("\n=== Step 2: AI response with function calls ===")
    print(f"Response: {response}")
    
    # Parse function calls
    from src.my_cli.core.function_calling.function_parser import parse_function_calls
    function_calls = parse_function_calls(response)
    
    print(f"\nFound {len(function_calls)} function calls:")
    for call in function_calls:
        print(f"  - {call.name}({call.arguments}) [ID: {call.id}]")
    
    # Execute the function calls
    from src.my_cli.core.function_calling.tool_executor import ToolExecutor
    
    # Create a simple config mock
    class MockConfig:
        def __init__(self):
            self.settings = type('Settings', (), {
                'auto_confirm_tools': True,
                'workspace_dirs': ['/share/xuzelai-nfs/projects/kimi-code']
            })()
    
    mock_config = MockConfig()
    tool_executor = ToolExecutor(tool_registry, mock_config)
    
    execution_results = await tool_executor.execute_function_calls(function_calls, auto_confirm=True)
    
    print(f"\n=== Step 3: Tool execution results ===")
    for result in execution_results:
        print(f"  - {result.function_call.name}: {'Success' if result.success else 'Failed'}")
        if result.success and result.result:
            print(f"    Output: {result.result.llm_content[:100]}...")
    
    # Create function response parts
    from src.my_cli.core.function_calling.result_processor import process_all_tool_results_for_ai
    tool_result_message_data = process_all_tool_results_for_ai(execution_results)
    
    print(f"\n=== Step 4: Function response message ===")
    print(f"Tool result message: {json.dumps(tool_result_message_data, indent=2)}")
    
    # First, add the AI's message with function calls to conversation history
    function_call_parts = []
    if response.candidates and response.candidates[0].content and "parts" in response.candidates[0].content:
        for part in response.candidates[0].content["parts"]:
            if isinstance(part, dict) and "function_call" in part:
                function_call_parts.append(MessagePart(function_call=part["function_call"]))
    
    ai_function_call_message = Message(
        role=MessageRole.MODEL,
        parts=function_call_parts
    )
    
    # Convert function results to Message format
    message_parts = []
    for part in tool_result_message_data["parts"]:
        if "function_response" in part:
            message_parts.append(MessagePart(function_response=part["function_response"]))
    
    tool_result_message = Message(
        role=MessageRole.MODEL,
        parts=message_parts
    )
    
    # Update conversation history with proper sequence
    conversation_history = [user_message, ai_function_call_message, tool_result_message]
    
    print(f"\n=== Step 5: Full conversation history before final response ===")
    for i, msg in enumerate(conversation_history):
        print(f"Message {i+1} ({msg.role.value}): {msg.dict()}")
    
    # Get final AI response
    print(f"\n=== Step 6: Getting final AI response ===")
    try:
        final_response = await content_generator.generate_content(conversation_history, tools=function_schemas)
        print(f"Final response: {final_response.text}")
    except Exception as e:
        print(f"Error getting final response: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini_conversation())