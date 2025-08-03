#!/usr/bin/env python3
"""Debug script to test direct Moonshot API calls."""

import asyncio
import os
import json
import httpx
from my_cli.core.client.kimi_generator import KimiContentGenerator
from my_cli.core.client.providers import KimiProviderConfig, AuthType, ModelProvider

async def test_direct_moonshot_api():
    """Test direct API call to Moonshot to compare behavior."""
    api_key = os.getenv('MY_CLI_KIMI_API_KEY')
    if not api_key:
        print("❌ MY_CLI_KIMI_API_KEY not found")
        return
    
    print(f"🔑 Using API key: {api_key[:10]}...")
    
    # Test 1: Direct API call using httpx
    print("\n📡 Testing direct Moonshot API call...")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Simple tool for testing
    tools = [{
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path"
                    }
                },
                "required": ["path"]
            }
        }
    }]
    
    request_data = {
        "model": "moonshot-v1-128k",
        "messages": [
            {"role": "system", "content": "You are Kimi, an AI assistant created by Moonshot AI."},
            {"role": "user", "content": "List the files in the current directory"}
        ],
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.6,
        "stream": False
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers=headers,
                json=request_data,
                timeout=30.0
            )
            
            print(f"📊 Status: {response.status_code}")
            print(f"📄 Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Response: {json.dumps(result, indent=2)}")
                
                # Check for tool calls
                if result.get("choices") and result["choices"][0].get("message", {}).get("tool_calls"):
                    print("🔧 Tool calls found!")
                    for tool_call in result["choices"][0]["message"]["tool_calls"]:
                        print(f"  - {tool_call['function']['name']}: {tool_call['function']['arguments']}")
                        
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"📝 Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Direct API call failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Our implementation
    print("\n🧪 Testing our KimiContentGenerator...")
    
    try:
        config = KimiProviderConfig(
            model="kimi-k2-instruct",
            provider=ModelProvider.KIMI,
            kimi_provider="moonshot",
            api_key=api_key,
            auth_type=AuthType.API_KEY
        )
        
        generator = KimiContentGenerator(config)
        await generator.initialize()
        
        print(f"🔗 Base URL: {generator._client.base_url}")
        print(f"🏷️ Model mapping: {generator._get_api_model_name('kimi-k2-instruct', 'moonshot')}")
        
        from my_cli.core.client.turn import Message, MessageRole
        from my_cli.core.function_calling.kimi_schema_generator import generate_kimi_function_schema
        from my_cli.tools.core.list_directory import ListDirectoryTool
        
        messages = [Message.create_text_message(MessageRole.USER, "List the files in the current directory")]
        
        list_tool = ListDirectoryTool()
        tool_schema = generate_kimi_function_schema(list_tool)
        tools = [tool_schema]
        
        response = await generator.generate_content(messages, tools=tools)
        print(f"✅ Our response: {response}")
        
    except Exception as e:
        print(f"❌ Our implementation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct_moonshot_api())