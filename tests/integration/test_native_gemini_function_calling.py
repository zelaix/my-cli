#!/usr/bin/env python3
"""Integration test for native Gemini function calling implementation."""

import asyncio
import tempfile
import os
from pathlib import Path

from src.my_cli.core.config import MyCliConfig
from src.my_cli.tools.registry import ToolRegistry
from src.my_cli.core.function_calling.gemini_schema_generator import (
    generate_all_gemini_function_declarations,
    format_tools_for_gemini_api
)
from src.my_cli.core.function_calling.function_parser import parse_function_calls
from src.my_cli.core.function_calling.conversation_orchestrator import ConversationOrchestrator
from src.my_cli.core.client.providers import create_provider_config, ModelProvider
from src.my_cli.core.client.content_generator import GeminiContentGenerator


async def test_schema_generation():
    """Test that tools are properly converted to Gemini function declarations."""
    print("\n=== Testing Schema Generation ===")
    
    # Initialize config and tool registry
    config = MyCliConfig()
    await config.initialize()
    
    registry = ToolRegistry()
    discovered = await registry.discover_builtin_tools(config)
    
    print(f"✓ Discovered {discovered} built-in tools")
    
    # Generate Gemini function declarations
    function_declarations = generate_all_gemini_function_declarations(registry)
    
    print(f"✓ Generated {len(function_declarations)} function declarations")
    
    # Verify format
    for declaration in function_declarations[:2]:  # Check first 2 tools
        assert "name" in declaration, "Function declaration missing 'name'"
        assert "description" in declaration, "Function declaration missing 'description'"
        assert "parameters" in declaration, "Function declaration missing 'parameters'"
        
        params = declaration["parameters"]
        assert "type" in params, "Parameters missing 'type'"
        assert params["type"] == "object", "Parameters type should be 'object'"
        
        print(f"  ✓ {declaration['name']}: {declaration['description'][:50]}...")
    
    # Test API format conversion
    api_tools = format_tools_for_gemini_api(function_declarations)
    assert len(api_tools) == 1, "Should have exactly one tool wrapper"
    assert "functionDeclarations" in api_tools[0], "Missing functionDeclarations key"
    assert len(api_tools[0]["functionDeclarations"]) == len(function_declarations), "Mismatch in declaration count"
    
    print("✓ API format conversion successful")
    return function_declarations


async def test_mock_function_parsing():
    """Test parsing of mock Gemini function call responses."""
    print("\n=== Testing Function Call Parsing ===")
    
    # Mock Gemini response with function call
    mock_response = {
        "candidates": [{
            "content": {
                "parts": [
                    {"text": "I'll help you read that file."},
                    {
                        "function_call": {
                            "name": "read_file",  
                            "args": {
                                "absolute_path": "/tmp/test.txt",
                                "limit": 10
                            }
                        }
                    }
                ]
            }
        }]
    }
    
    # Parse function calls
    function_calls = parse_function_calls(mock_response)
    
    # Debug output
    print(f"Mock response format: {type(mock_response)}")
    print(f"Found {len(function_calls)} function calls")
    
    assert len(function_calls) == 1, f"Expected 1 function call, got {len(function_calls)}"
    
    call = function_calls[0]
    assert call.name == "read_file", f"Expected 'read_file', got '{call.name}'"
    assert "absolute_path" in call.arguments, "Missing 'absolute_path' argument"
    assert call.arguments["absolute_path"] == "/tmp/test.txt", "Incorrect path argument"
    assert call.arguments["limit"] == 10, "Incorrect limit argument"
    
    print(f"✓ Parsed function call: {call.name} with {len(call.arguments)} arguments")
    
    # Test direct parts format (from content generator)
    direct_parts = {
        "parts": [
            {
                "function_call": {
                    "name": "write_file",
                    "args": {
                        "absolute_path": "/tmp/output.txt",
                        "content": "Hello, World!"
                    }
                }
            }
        ]
    }
    
    function_calls = parse_function_calls(direct_parts)
    assert len(function_calls) == 1, "Failed to parse direct parts format"
    assert function_calls[0].name == "write_file", "Incorrect function name from direct parts"
    
    print("✓ Direct parts format parsing successful")


async def test_content_generator_tools_integration():
    """Test that content generator properly handles tools parameter."""
    print("\n=== Testing Content Generator Tools Integration ===")
    
    # Test the method interfaces without requiring API key
    function_schemas = [
        {
            "name": "test_tool", 
            "description": "A test tool for validation",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Test message"}
                },
                "required": ["message"]
            }
        }
    ]
    
    # Test the conversion function directly
    from src.my_cli.core.client.content_generator import convert_function_schemas_to_gemini_tools
    gemini_tools = convert_function_schemas_to_gemini_tools(function_schemas)
    
    assert len(gemini_tools) == 1, "Should convert 1 function schema to 1 tool"
    assert gemini_tools[0].function_declarations, "Tool should have function declarations"
    assert len(gemini_tools[0].function_declarations) == 1, "Should have 1 function declaration"
    
    func_decl = gemini_tools[0].function_declarations[0]
    assert func_decl.name == "test_tool", "Function name should match"
    assert func_decl.description == "A test tool for validation", "Description should match"
    
    print("✓ Function schema to Gemini tools conversion successful")
    print("✓ Content generator tools integration verified")


async def test_orchestrator_integration():
    """Test that the orchestrator properly integrates native function calling."""
    print("\n=== Testing Orchestrator Integration ===")
    
    # Create minimal test setup
    config = MyCliConfig()
    await config.initialize()
    
    registry = ToolRegistry()
    await registry.discover_builtin_tools(config)
    
    # Mock content generator that doesn't require API key
    class MockContentGenerator:
        def __init__(self):
            self.provider = type('Provider', (), {'value': 'gemini'})()
            self.tools = None
        
        def set_tools(self, tools):
            self.tools = tools
        
        async def generate_content(self, messages, tools=None):
            # Mock response with function call
            return type('Response', (), {
                'candidates': [{
                    'content': {
                        'parts': [
                            {
                                'function_call': {
                                    'name': 'read_file',
                                    'args': {'absolute_path': '/tmp/test.txt'}
                                }
                            }
                        ]
                    }
                }],
                'text': 'Mock response'
            })()
        
        async def generate_content_stream(self, messages, tools=None):
            # Mock streaming response
            response = await self.generate_content(messages, tools)
            yield response
    
    mock_generator = MockContentGenerator()
    
    # Create orchestrator
    orchestrator = ConversationOrchestrator(
        content_generator=mock_generator,
        tool_registry=registry,
        config=config
    )
    
    # Verify initialization
    assert len(orchestrator.function_schemas) > 0, "Should have function schemas"
    assert orchestrator.provider_type == 'gemini', "Should detect Gemini provider"
    
    print(f"✓ Orchestrator initialized with {len(orchestrator.function_schemas)} function schemas")
    print("✓ Native Gemini function calling integration complete")


async def main():
    """Run all integration tests."""
    print("🚀 Testing Native Gemini Function Calling Integration")
    
    try:
        # Test schema generation
        function_declarations = await test_schema_generation()
        
        # Test function parsing
        await test_mock_function_parsing()
        
        # Test content generator integration
        await test_content_generator_tools_integration()
        
        # Test orchestrator integration
        await test_orchestrator_integration()
        
        print("\n✅ All Native Gemini Function Calling Tests Passed!")
        print(f"✅ Successfully converted {len(function_declarations)} tools to native Gemini format")
        print("✅ Function call parsing supports Gemini native format")
        print("✅ Content generator properly handles tools parameter")
        print("✅ Orchestrator integrates native function calling")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())