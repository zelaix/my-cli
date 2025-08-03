#!/usr/bin/env python3
"""Debug script to test Kimi tool calling directly."""

import asyncio
import os
from my_cli.core.client.kimi_generator import KimiContentGenerator
from my_cli.core.client.providers import KimiProviderConfig, AuthType
from my_cli.core.client.turn import Message, MessageRole
from my_cli.core.function_calling.kimi_schema_generator import generate_kimi_function_schema
from my_cli.tools.core.list_directory import ListDirectoryTool

async def main():
    """Test Kimi tool calling directly."""
    # Get API key
    api_key = os.getenv('MY_CLI_KIMI_API_KEY')
    if not api_key:
        print("❌ MY_CLI_KIMI_API_KEY not found")
        return
    
    # Create Kimi config
    from my_cli.core.client.providers import ModelProvider
    config = KimiProviderConfig(
        model="kimi-k2-instruct",
        provider=ModelProvider.KIMI,
        kimi_provider="moonshot", 
        api_key=api_key,
        auth_type=AuthType.API_KEY
    )
    
    # Create generator
    generator = KimiContentGenerator(config)
    await generator.initialize()
    
    # Create tool schema
    list_tool = ListDirectoryTool()
    tool_schema = generate_kimi_function_schema(list_tool)
    tools = [tool_schema]
    
    print(f"🔧 Tool schema: {tool_schema}")
    
    # Create message
    messages = [Message.create_text_message(MessageRole.USER, "List the files in the current directory")]
    
    try:
        # Test non-streaming first
        print("\n📤 Testing non-streaming generation...")
        response = await generator.generate_content(messages, tools=tools)
        print(f"✅ Response: {response}")
        
        # Check if response has function calls
        if response.candidates:
            candidate = response.candidates[0]
            print(f"🔍 Candidate content: {candidate.content}")
            
            if candidate.content and 'parts' in candidate.content:
                for i, part in enumerate(candidate.content['parts']):
                    print(f"  Part {i}: {part}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())