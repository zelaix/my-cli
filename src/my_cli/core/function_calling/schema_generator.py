"""JSON schema generation for AI function calling from tools."""

import json
from typing import Dict, Any, List, Optional
from ...tools.types import Tool
from ...tools.registry import ToolRegistry
from .gemini_schema_generator import (
    generate_gemini_function_declaration,
    generate_all_gemini_function_declarations,
    format_tools_for_provider as format_tools_for_provider_native
)


def generate_function_schema(tool: Tool) -> Dict[str, Any]:
    """
    Generate a function schema for AI function calling from a tool.
    
    DEPRECATED: Use generate_gemini_function_declaration for native Gemini function calling.
    
    Args:
        tool: Tool instance to generate schema for
        
    Returns:
        Function schema compatible with AI function calling APIs
    """
    # Use native Gemini function declaration for best compatibility
    return generate_gemini_function_declaration(tool)


def generate_all_function_schemas(registry: ToolRegistry) -> List[Dict[str, Any]]:
    """
    Generate function schemas for all tools in registry.
    
    DEPRECATED: Use generate_all_gemini_function_declarations for native Gemini function calling.
    
    Args:
        registry: Tool registry containing tools
        
    Returns:
        List of function schemas for AI function calling
    """
    return generate_all_gemini_function_declarations(registry)


def create_gemini_tool_config(schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Create Gemini-compatible tool configuration from function schemas.
    
    Args:
        schemas: List of function schemas
        
    Returns:
        Gemini tool configuration
    """
    if not schemas:
        return []
    
    return [{
        "function_declarations": schemas
    }]


def create_openai_tool_config(schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Create OpenAI-compatible tool configuration from function schemas.
    
    Args:
        schemas: List of function schemas
        
    Returns:
        OpenAI tool configuration  
    """
    return [
        {
            "type": "function",
            "function": schema
        }
        for schema in schemas
    ]


def format_tools_for_provider(schemas: List[Dict[str, Any]], provider: str) -> List[Dict[str, Any]]:
    """
    Format tool schemas for specific AI provider.
    
    Args:
        schemas: List of function schemas
        provider: Provider name ("gemini", "openai", "kimi")
        
    Returns:
        Provider-specific tool configuration
    """
    # Use native Gemini format for better compatibility
    return format_tools_for_provider_native(schemas, provider)


def validate_function_schema(schema: Dict[str, Any]) -> bool:
    """
    Validate a function schema for correctness.
    
    Args:
        schema: Function schema to validate
        
    Returns:
        True if schema is valid
    """
    required_fields = ["name", "description", "parameters"]
    
    # Check required top-level fields
    for field in required_fields:
        if field not in schema:
            return False
    
    # Validate parameters section
    parameters = schema["parameters"]
    if not isinstance(parameters, dict):
        return False
    
    if "type" not in parameters or parameters["type"] != "object":
        return False
    
    # Check properties exist if required is specified
    if "required" in parameters:
        if "properties" not in parameters:
            return False
        
        required_props = set(parameters["required"])
        available_props = set(parameters["properties"].keys())
        
        if not required_props.issubset(available_props):
            return False
    
    return True


def pretty_print_schemas(schemas: List[Dict[str, Any]]) -> str:
    """
    Pretty print function schemas for debugging.
    
    Args:
        schemas: List of function schemas
        
    Returns:
        Formatted JSON string
    """
    return json.dumps(schemas, indent=2, ensure_ascii=False)
