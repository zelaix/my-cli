"""
Integration tests for Kimi K2 tool calling functionality.

This module tests the complete integration of Kimi K2 models with the tool calling system,
ensuring that tools work correctly with both Gemini and Kimi providers.
"""

import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

from my_cli.core.client.kimi_generator import KimiContentGenerator
from my_cli.core.client.providers import KimiProviderConfig, ModelProvider, AuthType
from my_cli.core.function_calling.kimi_schema_generator import (
    generate_kimi_function_schema,
    format_tools_for_kimi_api,
    generate_all_kimi_function_schemas
)
from my_cli.core.function_calling.function_parser import parse_function_calls
from my_cli.core.function_calling.function_response_converter import (
    convert_to_function_response,
    detect_provider_from_content_generator
)
from my_cli.core.function_calling.agentic_orchestrator import AgenticOrchestrator
from my_cli.tools.registry import ToolRegistry
from my_cli.tools.core.read_file import ReadFileTool


class TestKimiSchemaGeneration:
    """Test Kimi schema generation functionality."""
    
    def test_kimi_schema_generation(self):
        """Test that Kimi schemas are generated correctly."""
        # Create a simple tool
        read_tool = ReadFileTool()
        
        # Generate Kimi schema
        kimi_schema = generate_kimi_function_schema(read_tool)
        
        # Verify schema structure
        assert kimi_schema["type"] == "function"
        assert "function" in kimi_schema
        assert kimi_schema["function"]["name"] == "read_file"
        assert "description" in kimi_schema["function"]
        assert "parameters" in kimi_schema["function"]
        
        # Verify parameters structure
        params = kimi_schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params
    
    def test_kimi_tools_formatting(self):
        """Test that tools are formatted correctly for Kimi API."""
        read_tool = ReadFileTool()
        registry = ToolRegistry()
        registry.register_tool(read_tool)
        
        # Generate all schemas
        schemas = generate_all_kimi_function_schemas(registry)
        
        # Format for API
        formatted_tools = format_tools_for_kimi_api(schemas)
        
        # Verify formatting
        assert isinstance(formatted_tools, list)
        assert len(formatted_tools) == 1
        assert formatted_tools[0]["type"] == "function"


class TestKimiFunctionParsing:
    """Test Kimi function call parsing."""
    
    def test_parse_openai_tool_calls(self):
        """Test parsing OpenAI-style tool calls from Kimi responses."""
        # Mock Kimi response with tool calls
        kimi_response = {
            "choices": [{
                "message": {
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"file_path": "/test/file.txt"}'
                        }
                    }]
                },
                "finish_reason": "tool_calls"
            }]
        }
        
        # Parse function calls
        function_calls = parse_function_calls(kimi_response)
        
        # Verify parsing
        assert len(function_calls) == 1
        call = function_calls[0]
        assert call.name == "read_file"
        assert call.arguments == {"file_path": "/test/file.txt"}
        assert call.id == "call_123"
    
    def test_parse_kimi_text_markers(self):
        """Test parsing Kimi's special text markers."""
        text_with_markers = """
        Let me read the file for you.
        
        <|tool_calls_section_begin|>
        <|tool_call_begin|>{"name": "read_file", "arguments": {"file_path": "/test/file.txt"}}<|tool_call_end|>
        <|tool_calls_section_end|>
        
        I'll process that now.
        """
        
        # Parse function calls
        function_calls = parse_function_calls(text_with_markers)
        
        # Verify parsing
        assert len(function_calls) == 1
        call = function_calls[0]
        assert call.name == "read_file"
        assert call.arguments == {"file_path": "/test/file.txt"}


class TestKimiResponseProcessing:
    """Test Kimi response processing and conversion."""
    
    def test_provider_detection(self):
        """Test provider detection from content generators."""
        # Mock Kimi content generator
        kimi_config = KimiProviderConfig(
            model="kimi-k2-instruct",
            kimi_provider="moonshot",
            api_key="test-key"
        )
        kimi_generator = KimiContentGenerator(kimi_config)
        
        # Detect provider
        provider = detect_provider_from_content_generator(kimi_generator)
        assert provider == "kimi"
    
    def test_kimi_response_conversion(self):
        """Test converting tool results to Kimi format."""
        # Test converting to Kimi format
        result = convert_to_function_response(
            tool_name="read_file",
            call_id="call_123",
            llm_content="File content here",
            provider="kimi"
        )
        
        # Verify Kimi format
        assert result["role"] == "tool"
        assert result["content"] == "File content here"
        assert result["tool_call_id"] == "call_123"
        assert result["name"] == "read_file"


class TestKimiAgenticIntegration:
    """Test complete agentic integration with Kimi models."""
    
    @pytest.mark.asyncio
    async def test_kimi_orchestrator_initialization(self):
        """Test that orchestrator initializes correctly with Kimi generator."""
        # Mock Kimi content generator
        kimi_config = KimiProviderConfig(
            model="kimi-k2-instruct",
            kimi_provider="moonshot",
            api_key="test-key"
        )
        kimi_generator = KimiContentGenerator(kimi_config)
        
        # Create tool registry with a simple tool
        registry = ToolRegistry()
        registry.register_tool(ReadFileTool())
        
        # Create orchestrator
        orchestrator = AgenticOrchestrator(
            content_generator=kimi_generator,
            tool_registry=registry,
            config=None
        )
        
        # Verify initialization
        assert orchestrator.provider == "kimi"
        assert len(orchestrator.function_schemas) == 1
        assert len(orchestrator.formatted_tools) == 1
        assert orchestrator.formatted_tools[0]["type"] == "function"
    
    @pytest.mark.asyncio 
    async def test_kimi_content_generator_tools_parameter(self):
        """Test that Kimi content generator accepts tools parameter."""
        # Mock Kimi content generator
        kimi_config = KimiProviderConfig(
            model="kimi-k2-instruct", 
            kimi_provider="moonshot",
            api_key="test-key"
        )
        kimi_generator = KimiContentGenerator(kimi_config)
        
        # Mock the HTTP client to avoid actual API calls
        with patch.object(kimi_generator, '_client') as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{
                    "message": {"content": "Hello world"},
                    "finish_reason": "stop"
                }],
                "usage": {"total_tokens": 10, "prompt_tokens": 5, "completion_tokens": 5}
            }
            mock_client.post = AsyncMock(return_value=mock_response)
            
            # Initialize generator
            await kimi_generator.initialize()
            
            # Create tools
            read_tool = ReadFileTool()
            tools = [generate_kimi_function_schema(read_tool)]
            
            # Test generation with tools
            from my_cli.core.client.turn import Message, MessageRole
            messages = [Message.create_text_message(MessageRole.USER, "Test message")]
            
            # This should not raise an error
            response = await kimi_generator.generate_content(messages, tools=tools)
            
            # Verify tools were passed to request
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            request_data = call_args[1]['json']
            
            assert 'tools' in request_data
            assert len(request_data['tools']) == 1
            assert request_data['tools'][0]['type'] == 'function'


# Test configuration for pytest
@pytest.fixture
def mock_kimi_api_key():
    """Provide mock API key for testing."""
    return "test-kimi-api-key"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])