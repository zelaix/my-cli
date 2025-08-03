#!/usr/bin/env python3
"""
Standalone test for single-step function calling.
Tests the exact same pattern as the original Gemini CLI.

Usage:
  python test_function_calling.py              # Clean output
  MY_CLI_DEBUG=1 python test_function_calling.py  # Debug output
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

async def test_single_function_call():
    """Test basic function calling without orchestrator complexity."""
    
    # Set up API key
    api_key = os.getenv("MY_CLI_API_KEY")
    if not api_key:
        print("Error: MY_CLI_API_KEY environment variable not set")
        return False
    
    print("🔧 Creating content generator...")
    
    # Create content generator
    content_generator = create_gemini_content_generator(
        model="gemini-2.0-flash-exp",
        auth_type=AuthType.API_KEY,
        api_key=api_key
    )
    
    await content_generator.initialize()
    print("✅ Content generator initialized")
    
    # Create tool registry with just one simple tool
    print("🔧 Setting up tools...")
    tool_registry = ToolRegistry()
    discovered = await tool_registry.discover_builtin_tools()
    print(f"✅ Discovered {discovered} tools")
    
    # Generate function schemas
    from my_cli.core.function_calling.gemini_schema_generator import generate_all_gemini_function_declarations
    schemas = generate_all_gemini_function_declarations(tool_registry)
    print(f"✅ Generated {len(schemas)} function schemas")
    
    # Print the schemas for debugging
    for schema in schemas:
        print(f"  - {schema['name']}: {schema['description']}")
    
    # Set tools on content generator
    tools = [{"functionDeclarations": schemas}] if schemas else []
    content_generator.set_tools(tools)
    print("✅ Tools configured on model")
    
    # Create a simple message
    print("\n🔧 Testing function calling...")
    messages = [
        Message(
            role=MessageRole.USER,
            parts=[MessagePart(text="Please call the list_directory function with dir_path='/share/xuzelai-nfs/projects/kimi-code' to list the files")]
        )
    ]
    
    print("📤 Sending message to AI...")
    print("Message: List the files in the current directory using the list_directory function")
    
    # Test streaming response
    function_calls_found = []
    text_content = ""
    
    async for chunk in content_generator.generate_content_stream(messages):
        if chunk.text:
            text_content += chunk.text
            print(f"📝 Text: {chunk.text}", end="")
        
        if chunk.function_calls:
            for fc in chunk.function_calls:
                function_calls_found.append(fc)
                print(f"📞 Function call: {fc}")
    
    print(f"\n\n✅ Test completed!")
    print(f"📊 Results:")
    print(f"  - Text content: {len(text_content)} chars")
    print(f"  - Function calls found: {len(function_calls_found)}")
    
    if function_calls_found:
        print("🎉 SUCCESS: AI made function calls!")
        for i, fc in enumerate(function_calls_found):
            print(f"  Call {i+1}: {fc['name']}({fc.get('args', {})})")
        return True
    else:
        print("❌ FAILURE: AI did not make function calls")
        print(f"   Instead got text: {text_content}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_single_function_call())
    sys.exit(0 if success else 1)