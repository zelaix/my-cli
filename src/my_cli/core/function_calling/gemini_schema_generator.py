"""Native Gemini function calling schema generation for AI-tool integration."""

from typing import Dict, Any, List, Optional, Union
from ...tools.types import Tool
from ...tools.registry import ToolRegistry


def clean_schema_for_gemini(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean a JSON schema to be compatible with Gemini's native function calling.
    
    Gemini's function calling supports these JSON Schema fields:
    - type, description, properties, required, items (for arrays)
    - enum (for string enums)
    - Does not support: minimum, maximum, default, additionalProperties, etc.
    """
    if not isinstance(schema, dict):
        return schema
    
    cleaned = {}
    
    # Keep only supported fields for Gemini function calling
    supported_fields = {"type", "description", "properties", "required", "items", "enum"}
    
    for key, value in schema.items():
        if key in supported_fields:
            if key == "properties" and isinstance(value, dict):
                # Recursively clean property schemas
                cleaned[key] = {
                    prop_name: clean_schema_for_gemini(prop_schema)
                    for prop_name, prop_schema in value.items()
                }
            elif key == "items" and isinstance(value, dict):
                # Clean array item schema
                cleaned[key] = clean_schema_for_gemini(value)
            else:
                cleaned[key] = value
    
    return cleaned


def generate_gemini_function_declaration(tool: Tool) -> Dict[str, Any]:
    """
    Generate a native Gemini FunctionDeclaration from a tool.
    
    This matches the exact format expected by Google's Gemini API:
    {
        "name": "function_name",
        "description": "Function description", 
        "parameters": {
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }
    
    Args:
        tool: Tool instance to generate declaration for
        
    Returns:
        Native Gemini FunctionDeclaration dictionary
    """
    # Start with the tool's schema and clean it for Gemini
    parameters = clean_schema_for_gemini(tool.schema.copy())
    
    # Ensure proper JSON Schema object format
    if "type" not in parameters:
        parameters["type"] = "object"
    
    # Create native Gemini FunctionDeclaration
    function_declaration = {
        "name": tool.name,
        "description": tool.description,
        "parameters": parameters
    }
    
    return function_declaration


def format_tools_for_gemini_api(function_declarations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format function declarations for Gemini API tools parameter.
    
    The Gemini API expects tools in this format:
    [
        {
            "functionDeclarations": [
                {"name": "...", "description": "...", "parameters": {...}},
                ...
            ]
        }
    ]
    
    Args:
        function_declarations: List of function declarations
        
    Returns:
        Tools list formatted for Gemini API
    """
    if not function_declarations:
        return []
    
    return [{"functionDeclarations": function_declarations}]


def generate_all_gemini_function_declarations(tool_registry: ToolRegistry) -> List[Dict[str, Any]]:
    """
    Generate native Gemini function declarations for all tools in registry.
    
    Args:
        tool_registry: Registry containing tools
        
    Returns:
        List of Gemini FunctionDeclarations
    """
    declarations = []
    
    for tool in tool_registry.get_all_tools():
        declaration = generate_gemini_function_declaration(tool)
        declarations.append(declaration)
    
    return declarations


def format_tools_for_provider(
    function_declarations: List[Dict[str, Any]], 
    provider: str
) -> List[Dict[str, Any]]:
    """
    Format function declarations for specific AI provider.
    
    Args:
        function_declarations: List of function declarations (Gemini format)
        provider: Provider name ('gemini', 'kimi', etc.)
        
    Returns:
        Tools formatted for the specific provider
    """
    if provider.lower() == 'gemini':
        return format_tools_for_gemini_api(function_declarations)
    elif provider.lower() == 'kimi':
        # Convert Gemini declarations to Kimi/OpenAI format
        from .kimi_schema_generator import convert_gemini_to_kimi_schema, format_tools_for_kimi_api
        kimi_schemas = [convert_gemini_to_kimi_schema(decl) for decl in function_declarations]
        return format_tools_for_kimi_api(kimi_schemas)
    else:
        # Default format for unknown providers (use Gemini format)
        return format_tools_for_gemini_api(function_declarations)


# Backward compatibility aliases
generate_gemini_function_schema = generate_gemini_function_declaration
generate_all_gemini_function_schemas = generate_all_gemini_function_declarations