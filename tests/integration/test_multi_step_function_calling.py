#!/usr/bin/env python3
"""
Test multi-step function calling with agentic orchestration.
Tests the complete implementation including Turn.run() and automatic continuation.

Usage:
  python test_multi_step_function_calling.py              # Clean output
  MY_CLI_DEBUG=1 python test_multi_step_function_calling.py  # Debug output
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

async def test_multi_step_function_calling():
    """Test multi-step agentic tool calling with orchestrator."""
    
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
    
    # Create tool registry
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
    
    # Create agentic orchestrator
    print("🔧 Creating agentic orchestrator...")
    
    # Create a simple config object for the orchestrator
    class SimpleConfig:
        def get_auto_confirm_tools(self):
            return True  # Auto-confirm all tools for testing
    
    config = SimpleConfig()
    orchestrator = AgenticOrchestrator(content_generator, tool_registry, config)
    print("✅ Orchestrator created")
    
    # Test multi-step conversation
    print("\n🔧 Testing multi-step function calling...")
    initial_message = "Please analyze the current directory by first listing all files, then read the README.md file to understand what this project is about."
    
    print(f"📤 Sending message: {initial_message}")
    
    # Run the multi-step conversation
    async for event in orchestrator.send_message(initial_message):
        event_type = str(event.type)
        
        if event_type == "content":
            print(f"📝 AI: {event.value}", end="")
        elif event_type == "tool_call_request":
            tool_info = event.value
            print(f"\n🔧 Tool call requested: {tool_info.name} with args: {tool_info.args}")
        elif event_type == "tool_call_response":
            result = event.value
            if result.success:
                print(f"✅ Tool completed successfully")
            else:
                print(f"❌ Tool failed: {result.error}")
        elif event_type == "finished":
            print(f"\n🎉 Conversation completed!")
            return True
        elif event_type == "error":
            print(f"\n❌ Error: {event.value}")
            return False
        else:
            print(f"\n🔍 Event: {event_type} - {event.value}")
    
    print("\n✅ Multi-step test completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_multi_step_function_calling())
    sys.exit(0 if success else 1)