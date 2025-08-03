#!/usr/bin/env python3
"""
Debug conversation history to understand function call/response mismatch.
"""

import asyncio
import os
import sys
import json
import logging

# Set up logging - only show warnings/errors unless debug mode is enabled
log_level = logging.DEBUG if os.getenv("MY_CLI_DEBUG") else logging.WARNING
logging.basicConfig(level=log_level, format='%(name)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, '/share/xuzelai-nfs/projects/kimi-code/src')

from my_cli.core.client.content_generator import create_gemini_content_generator, AuthType
from my_cli.core.client.turn import Message, MessageRole, MessagePart
from my_cli.tools.registry import ToolRegistry
from my_cli.core.function_calling.agentic_orchestrator import AgenticOrchestrator
from my_cli.core.function_calling.gemini_schema_generator import generate_all_gemini_function_declarations

async def debug_conversation_flow():
    """Debug the exact conversation history and API calls."""
    
    # Set up API key
    api_key = os.getenv("MY_CLI_API_KEY")
    if not api_key:
        print("Error: MY_CLI_API_KEY environment variable not set")
        return False
    
    print("🔧 Creating content generator...")
    
    # Create content generator with debug logging
    content_generator = create_gemini_content_generator(
        model="gemini-2.0-flash-exp",
        auth_type=AuthType.API_KEY,
        api_key=api_key
    )
    
    await content_generator.initialize()
    print("✅ Content generator initialized")
    
    # Create tool registry with just one tool for simplicity
    print("🔧 Setting up tools...")
    tool_registry = ToolRegistry()
    discovered = await tool_registry.discover_builtin_tools()
    print(f"✅ Discovered {discovered} tools")
    
    # Generate function schemas
    schemas = generate_all_gemini_function_declarations(tool_registry)
    print(f"✅ Generated {len(schemas)} function schemas")
    
    # Set tools on content generator
    tools = [{"functionDeclarations": schemas}] if schemas else []
    content_generator.set_tools(tools)
    print("✅ Tools configured on model")
    
    # Create a simple message that will trigger ONE tool call
    print("\n🔧 Testing single function call...")
    messages = [
        Message(
            role=MessageRole.USER,
            parts=[MessagePart(text="List the files in /share/xuzelai-nfs/projects/kimi-code")]
        )
    ]
    
    print("📤 First API call - Initial user message")
    print("Messages being sent:")
    for i, msg in enumerate(messages):
        print(f"  Message {i+1}: {msg.role.value}")
        for j, part in enumerate(msg.parts):
            if part.text:
                print(f"    Part {j+1}: text = '{part.text[:50]}...'")
            elif part.function_call:
                print(f"    Part {j+1}: function_call = {part.function_call}")
            elif part.function_response:
                print(f"    Part {j+1}: function_response = {part.function_response}")
    
    # Get first response (should contain function call)
    function_calls_found = []
    ai_response_parts = []
    
    async for chunk in content_generator.generate_content_stream(messages):
        if chunk.text:
            ai_response_parts.append(MessagePart(text=chunk.text))
        
        if chunk.function_calls:
            for fc in chunk.function_calls:
                function_calls_found.append(fc)
                ai_response_parts.append(MessagePart(function_call=fc))
    
    print(f"\n📥 First API response:")
    print(f"  - Function calls: {len(function_calls_found)}")
    print(f"  - AI response parts: {len(ai_response_parts)}")
    
    if not function_calls_found:
        print("❌ No function calls found, test cannot continue")
        return False
    
    # Simulate tool execution result
    call_id = function_calls_found[0]['id']
    tool_name = function_calls_found[0]['name']
    
    print(f"\n🔧 Simulating tool execution for call_id: {call_id}")
    
    # Create function response part
    function_response_part = MessagePart(
        function_response={
            "id": call_id,
            "name": tool_name,
            "response": {
                "output": "Directory contains: README.md, src/, tests/, etc."
            }
        }
    )
    
    # Now build the conversation history as it would be at continuation time
    print("\n📝 Building conversation history for continuation:")
    
    # Add initial user message
    conversation_history = [
        Message(role=MessageRole.USER, parts=[MessagePart(text="List the files in /share/xuzelai-nfs/projects/kimi-code")])
    ]
    print(f"  1. USER: List the files in /share/xuzelai-nfs/projects/kimi-code")
    
    # Add AI response with function call
    ai_message = Message(role=MessageRole.MODEL, parts=ai_response_parts)
    conversation_history.append(ai_message)
    print(f"  2. MODEL: {len(ai_response_parts)} parts (including function call)")
    
    # Add function response as USER message
    function_response_message = Message(role=MessageRole.USER, parts=[function_response_part])
    conversation_history.append(function_response_message)
    print(f"  3. USER: 1 function_response part")
    
    print(f"\n📊 Conversation analysis:")
    print(f"  - Total messages: {len(conversation_history)}")
    
    # Find MODEL message with function calls
    model_messages_with_calls = []
    for i, msg in enumerate(conversation_history):
        if msg.role == MessageRole.MODEL:
            function_call_count = sum(1 for part in msg.parts if part.function_call)
            if function_call_count > 0:
                model_messages_with_calls.append((i, function_call_count))
                print(f"  - Message {i+1} (MODEL): {function_call_count} function calls")
    
    # Find USER messages with function responses
    user_messages_with_responses = []
    for i, msg in enumerate(conversation_history):
        if msg.role == MessageRole.USER:
            function_response_count = sum(1 for part in msg.parts if part.function_response)
            if function_response_count > 0:
                user_messages_with_responses.append((i, function_response_count))
                print(f"  - Message {i+1} (USER): {function_response_count} function responses")
    
    print(f"\n🔍 Function call/response pairing analysis:")
    if len(model_messages_with_calls) == 1 and len(user_messages_with_responses) == 1:
        model_calls = model_messages_with_calls[0][1]
        user_responses = user_messages_with_responses[0][1]
        print(f"  - MODEL function calls: {model_calls}")
        print(f"  - USER function responses: {user_responses}")
        if model_calls == user_responses:
            print("  ✅ Counts match!")
        else:
            print("  ❌ COUNT MISMATCH!")
    else:
        print(f"  ❌ Unexpected conversation structure!")
    
    print(f"\n📤 Second API call - Continuation with tool results")
    print("Testing if this conversation history causes the error...")
    
    try:
        # Try to continue the conversation
        async for chunk in content_generator.generate_content_stream(conversation_history):
            if chunk.text:
                print(f"📝 AI: {chunk.text}", end="")
            elif chunk.function_calls:
                print(f"\n📞 More function calls: {len(chunk.function_calls)}")
        print("\n✅ Continuation successful!")
        return True
    except Exception as e:
        print(f"\n❌ Continuation failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(debug_conversation_flow())
    sys.exit(0 if success else 1)