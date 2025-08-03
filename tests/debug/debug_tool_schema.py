#!/usr/bin/env python3
"""Debug script to check tool schema sent to Kimi API."""

import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from my_cli.core.client.kimi_generator import KimiContentGenerator
from my_cli.core.client.providers import KimiProviderConfig, AuthType, ModelProvider
from my_cli.core.client.turn import Message, MessageRole
from my_cli.core.function_calling.kimi_schema_generator import generate_kimi_function_schema
from my_cli.tools.core.list_directory import ListDirectoryTool

async def debug_tool_schema():
    """Debug the tool schema being sent to Kimi API."""
    print("🔍 Debugging tool schema sent to Kimi API...")
    
    # Create the tool and generate schema
    list_tool = ListDirectoryTool()
    print(f"📋 Tool info:")
    print(f"  Name: {list_tool.name}")
    print(f"  Description: {list_tool.description}")
    print(f"  Schema: {json.dumps(list_tool.schema, indent=2)}")
    
    # Generate Kimi schema
    tool_schema = generate_kimi_function_schema(list_tool)
    print(f"\n🔧 Generated Kimi schema:")
    print(json.dumps(tool_schema, indent=2))
    
    # Check if the schema has proper parameters
    function_def = tool_schema.get('function', {})
    parameters = function_def.get('parameters', {})
    print(f"\n📊 Schema analysis:")
    print(f"  Function name: {function_def.get('name', 'MISSING')}")
    print(f"  Function description: {function_def.get('description', 'MISSING')}")
    print(f"  Parameters type: {parameters.get('type', 'MISSING')}")
    print(f"  Properties: {list(parameters.get('properties', {}).keys())}")
    print(f"  Required: {parameters.get('required', [])}")
    
    # Test actual API call
    api_key = os.getenv('MY_CLI_KIMI_API_KEY')
    if not api_key:
        print("❌ MY_CLI_KIMI_API_KEY not found")
        return
    
    config = KimiProviderConfig(
        model="kimi-k2-base",
        provider=ModelProvider.KIMI,
        kimi_provider="moonshot",
        api_key=api_key,
        auth_type=AuthType.API_KEY
    )
    
    generator = KimiContentGenerator(config)
    await generator.initialize()
    
    tools = [tool_schema]
    messages = [Message.create_text_message(MessageRole.USER, "List the files in the current directory")]
    
    print(f"\n📤 Making API call with tools...")
    print(f"  Tools count: {len(tools)}")
    print(f"  Message: {messages[0].get_text_content()}")
    
    try:
        response = await generator.generate_content(messages, tools=tools)
        print(f"\n✅ API Response:")
        print(f"  Function calls: {len(response.function_calls)}")
        
        for i, func_call in enumerate(response.function_calls):
            print(f"  Call {i+1}:")
            print(f"    ID: {func_call.get('id', 'NO_ID')}")
            print(f"    Name: {func_call.get('name', 'NO_NAME')}")
            print(f"    Args: {func_call.get('args', 'NO_ARGS')}")
            print(f"    Args type: {type(func_call.get('args', 'NO_ARGS'))}")
            
            # Check if args has the expected 'path' parameter
            args = func_call.get('args', {})
            if isinstance(args, dict) and 'path' in args:
                print(f"    ✅ Has path parameter: {args['path']}")
            else:
                print(f"    ❌ Missing path parameter!")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_tool_schema())