"""
Kimi K2 function calling schema generation for OpenAI-compatible tool format.

This module provides schema generation for Kimi K2 models that use the OpenAI-compatible
tools format, converting internal tool schemas to the format expected by Kimi API.
"""

from typing import Dict, Any, List, Optional
from ...tools.types import Tool
from ...tools.registry import ToolRegistry


def generate_kimi_function_schema(tool: Tool) -> Dict[str, Any]:
    """
    Generate an OpenAI-compatible function schema from a tool for Kimi K2.
    
    Kimi K2 uses the OpenAI tools format:
    {
        "type": "function",
        "function": {
            "name": "function_name",
            "description": "Function description",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    }
    
    Args:
        tool: Tool instance to generate schema for
        
    Returns:
        OpenAI-compatible tool schema dictionary
    """
    # Start with the tool's schema and clean it for OpenAI compatibility
    parameters = clean_schema_for_openai(tool.schema.copy())
    
    # Ensure proper JSON Schema object format
    if "type" not in parameters:
        parameters["type"] = "object"
    
    # Create OpenAI-compatible tool schema
    tool_schema = {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": parameters
        }
    }
    
    return tool_schema


def clean_schema_for_openai(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean a JSON schema to be compatible with OpenAI-style function calling.
    
    OpenAI's function calling supports most JSON Schema fields but has some limitations.
    This function ensures compatibility with Kimi K2's OpenAI-compatible API.
    
    Args:
        schema: Original JSON schema
        
    Returns:
        Cleaned schema compatible with OpenAI format
    """
    if not isinstance(schema, dict):
        return schema
    
    cleaned = {}
    
    # OpenAI supports most JSON Schema fields
    # We'll be conservative and only include well-supported fields
    supported_fields = {
        "type", "description", "properties", "required", "items", 
        "enum", "minimum", "maximum", "minLength", "maxLength",
        "pattern", "format", "default"
    }
    
    for key, value in schema.items():
        if key in supported_fields:
            if key == "properties" and isinstance(value, dict):
                # Recursively clean property schemas
                cleaned[key] = {
                    prop_name: clean_schema_for_openai(prop_schema)
                    for prop_name, prop_schema in value.items()
                }
            elif key == "items" and isinstance(value, dict):
                # Clean array item schema
                cleaned[key] = clean_schema_for_openai(value)
            else:
                cleaned[key] = value
    
    return cleaned


def format_tools_for_kimi_api(tool_schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format tool schemas for Kimi K2 API tools parameter.
    
    Kimi K2 expects tools in OpenAI format:
    [
        {
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {...}
            }
        },
        ...
    ]
    
    Args:
        tool_schemas: List of tool schemas
        
    Returns:
        Tools list formatted for Kimi K2 API
    """
    # Kimi uses the schemas directly, no wrapping needed
    return tool_schemas


def generate_all_kimi_function_schemas(tool_registry: ToolRegistry) -> List[Dict[str, Any]]:
    """
    Generate OpenAI-compatible function schemas for all tools in registry.
    
    Args:
        tool_registry: Registry containing tools
        
    Returns:
        List of OpenAI-compatible tool schemas
    """
    schemas = []
    
    for tool in tool_registry.get_all_tools():
        schema = generate_kimi_function_schema(tool)
        schemas.append(schema)
    
    return schemas


def convert_gemini_to_kimi_schema(gemini_declaration: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a Gemini function declaration to Kimi/OpenAI format.
    
    Args:
        gemini_declaration: Gemini FunctionDeclaration
        
    Returns:
        OpenAI-compatible tool schema
    """
    return {
        "type": "function",
        "function": {
            "name": gemini_declaration["name"],
            "description": gemini_declaration["description"],
            "parameters": gemini_declaration["parameters"]
        }
    }


def convert_kimi_to_gemini_schema(kimi_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a Kimi/OpenAI tool schema to Gemini function declaration.
    
    Args:
        kimi_schema: OpenAI-compatible tool schema
        
    Returns:
        Gemini FunctionDeclaration
    """
    if "function" not in kimi_schema:
        raise ValueError("Invalid Kimi tool schema: missing 'function' key")
    
    function = kimi_schema["function"]
    
    return {
        "name": function["name"],
        "description": function["description"],
        "parameters": function["parameters"]
    }


def format_tools_for_provider(
    tool_schemas: List[Dict[str, Any]], 
    provider: str
) -> List[Dict[str, Any]]:
    """
    Format tool schemas for specific AI provider.
    
    Args:
        tool_schemas: List of tool schemas (in internal format)
        provider: Provider name ('gemini', 'kimi', etc.)
        
    Returns:
        Tools formatted for the specific provider
    """
    if provider.lower() == 'gemini':
        # Convert to Gemini format if needed
        from .gemini_schema_generator import format_tools_for_gemini_api
        
        # If schemas are already in Kimi format, convert them
        gemini_declarations = []
        for schema in tool_schemas:
            if "function" in schema and "type" in schema:
                # It's a Kimi/OpenAI schema, convert to Gemini
                gemini_decl = convert_kimi_to_gemini_schema(schema)
                gemini_declarations.append(gemini_decl)
            else:
                # Assume it's already a Gemini declaration
                gemini_declarations.append(schema)
        
        return format_tools_for_gemini_api(gemini_declarations)
    
    elif provider.lower() == 'kimi':
        # Ensure schemas are in Kimi/OpenAI format
        kimi_schemas = []
        for schema in tool_schemas:
            if "function" in schema and "type" in schema:
                # Already in Kimi format
                kimi_schemas.append(schema)
            else:
                # Assume it's a Gemini declaration, convert to Kimi
                kimi_schema = convert_gemini_to_kimi_schema(schema)
                kimi_schemas.append(kimi_schema)
        
        return format_tools_for_kimi_api(kimi_schemas)
    
    else:
        # Default format for unknown providers (use Kimi/OpenAI format)
        return tool_schemas


def validate_kimi_tool_schema(schema: Dict[str, Any]) -> bool:
    """
    Validate a Kimi/OpenAI tool schema.
    
    Args:
        schema: Tool schema to validate
        
    Returns:
        True if schema is valid
    """
    # Check required top-level fields
    if not isinstance(schema, dict):
        return False
    
    if schema.get("type") != "function":
        return False
    
    function = schema.get("function")
    if not isinstance(function, dict):
        return False
    
    # Check required function fields
    required_fields = ["name", "description", "parameters"]
    for field in required_fields:
        if field not in function:
            return False
    
    # Validate parameters schema
    parameters = function["parameters"]
    if not isinstance(parameters, dict):
        return False
    
    if parameters.get("type") != "object":
        return False
    
    return True


def get_tool_names_from_schemas(schemas: List[Dict[str, Any]]) -> List[str]:
    """
    Extract tool names from Kimi/OpenAI tool schemas.
    
    Args:
        schemas: List of tool schemas
        
    Returns:
        List of tool names
    """
    names = []
    for schema in schemas:
        if validate_kimi_tool_schema(schema):
            names.append(schema["function"]["name"])
    return names


# Backward compatibility aliases
generate_kimi_function_declaration = generate_kimi_function_schema
generate_all_kimi_function_declarations = generate_all_kimi_function_schemas