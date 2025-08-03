"""
Enhanced content generator for My CLI with multi-provider support.

This module provides sophisticated content generation with multiple AI providers,
authentication methods, streaming support, and integration with the original 
Gemini CLI patterns.
"""

import asyncio
import logging
import os
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from pathlib import Path

import google.generativeai as genai
from google.oauth2 import service_account
from google.auth import default

from .providers import (
    BaseContentGenerator,
    GeminiProviderConfig,
    KimiProviderConfig, 
    GenerateContentResponse,
    GenerationCandidate,
    UsageMetadata,
    ModelProvider,
    AuthType,
    detect_provider_from_model,
    create_provider_config
)
from .errors import (
    GeminiError,
    AuthenticationError,
    ConfigurationError,
    classify_error,
)
from .retry import RetryManager, RetryConfig
from .turn import Message, MessageRole, MessagePart, Turn

logger = logging.getLogger(__name__)


def convert_json_schema_to_gemini_schema(json_schema: Dict[str, Any]) -> genai.protos.Schema:
    """Convert JSON schema to Gemini protobuf Schema format."""
    schema_type = genai.protos.Type.OBJECT  # Default to object
    
    # Map JSON schema types to Gemini types
    if json_schema.get("type") == "string":
        schema_type = genai.protos.Type.STRING
    elif json_schema.get("type") == "integer":
        schema_type = genai.protos.Type.INTEGER
    elif json_schema.get("type") == "number":
        schema_type = genai.protos.Type.NUMBER
    elif json_schema.get("type") == "boolean":
        schema_type = genai.protos.Type.BOOLEAN
    elif json_schema.get("type") == "array":
        schema_type = genai.protos.Type.ARRAY
    elif json_schema.get("type") == "object":
        schema_type = genai.protos.Type.OBJECT
    
    # Create base schema
    schema = genai.protos.Schema(
        type=schema_type,
        description=json_schema.get("description", "")
    )
    
    # Handle object properties
    if json_schema.get("type") == "object" and "properties" in json_schema:
        properties = {}
        for prop_name, prop_schema in json_schema["properties"].items():
            properties[prop_name] = convert_json_schema_to_gemini_schema(prop_schema)
        schema.properties.update(properties)
        
        # Handle required fields
        if "required" in json_schema:
            schema.required.extend(json_schema["required"])
    
    return schema


def convert_function_schemas_to_gemini_tools(function_schemas: List[Dict[str, Any]]) -> List[genai.protos.Tool]:
    """Convert function schemas to Gemini Tool protobuf format."""
    if not function_schemas:
        return []
    
    # Create all function declarations
    func_declarations = []
    for func_schema in function_schemas:
        func_declaration = genai.protos.FunctionDeclaration(
            name=func_schema["name"],
            description=func_schema["description"],
            parameters=convert_json_schema_to_gemini_schema(func_schema["parameters"])
        )
        func_declarations.append(func_declaration)
    
    # Create a single tool with all function declarations
    tool = genai.protos.Tool(function_declarations=func_declarations)
    return [tool]

# Re-export common types for backward compatibility
ContentGenerator = BaseContentGenerator


class GeminiContentGenerator(BaseContentGenerator):
    """Enhanced content generator for Google Gemini API."""
    
    def __init__(self, config: GeminiProviderConfig):
        super().__init__(config)
        self.config: GeminiProviderConfig = config
        self._client: Optional[genai.GenerativeModel] = None
        self._chat_session: Optional[Any] = None
        
        # Initialize retry manager
        self.retry_manager = RetryManager(config.retry_config or RetryConfig())
    
    async def initialize(self) -> None:
        """Initialize the Gemini client with authentication."""
        if self._initialized:
            return
        
        try:
            await self._configure_authentication()
            await self._create_model()
            self._initialized = True
            logger.info(f"Initialized Gemini content generator with model {self.config.model}")
            
        except Exception as e:
            error = classify_error(e)
            logger.error(f"Failed to initialize content generator: {error}")
            raise error
    
    async def _configure_authentication(self) -> None:
        """Configure authentication based on auth type."""
        try:
            if self.config.auth_type == AuthType.API_KEY:
                if not self.config.api_key:
                    # Try to get from environment
                    api_key = os.getenv("MY_CLI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                    if not api_key:
                        raise AuthenticationError(
                            "API key is required. Set MY_CLI_API_KEY environment variable or provide api_key in config.",
                            auth_type="api_key"
                        )
                    self.config.api_key = api_key
                
                genai.configure(api_key=self.config.api_key)
                
            elif self.config.auth_type == AuthType.APPLICATION_DEFAULT_CREDENTIALS:
                # Use Application Default Credentials
                credentials, project = default()
                genai.configure(credentials=credentials)
                if not self.config.project_id and project:
                    self.config.project_id = project
                    
            elif self.config.auth_type == AuthType.SERVICE_ACCOUNT:
                if not self.config.service_account_path:
                    raise AuthenticationError(
                        "Service account path is required for service account authentication",
                        auth_type="service_account"
                    )
                
                service_account_path = Path(self.config.service_account_path)
                if not service_account_path.exists():
                    raise AuthenticationError(
                        f"Service account file not found: {service_account_path}",
                        auth_type="service_account"
                    )
                
                credentials = service_account.Credentials.from_service_account_file(
                    str(service_account_path),
                    scopes=["https://www.googleapis.com/auth/generative-language"]
                )
                genai.configure(credentials=credentials)
                
            elif self.config.auth_type == AuthType.VERTEX_AI:
                if not self.config.project_id:
                    raise AuthenticationError(
                        "Project ID is required for Vertex AI authentication",
                        auth_type="vertex_ai"
                    )
                
                # Import Vertex AI client
                try:
                    import vertexai
                    vertexai.init(
                        project=self.config.project_id,
                        location=self.config.location or "us-central1"
                    )
                except ImportError:
                    raise ConfigurationError(
                        "vertexai package is required for Vertex AI authentication. Install with: pip install google-cloud-aiplatform"
                    )
                
            elif self.config.auth_type == AuthType.OAUTH:
                # OAuth flow would be implemented here
                raise ConfigurationError("OAuth authentication not yet implemented")
                
            else:
                raise ConfigurationError(f"Unsupported authentication type: {self.config.auth_type}")
                
        except Exception as e:
            if isinstance(e, (AuthenticationError, ConfigurationError)):
                raise
            raise classify_error(e)
    
    async def _create_model(self) -> None:
        """Create the generative model with configuration."""
        try:
            # Prepare generation config
            generation_config = {
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens,
                "top_p": self.config.top_p,
                "top_k": self.config.top_k,
            }
            
            if self.config.stop_sequences:
                generation_config["stop_sequences"] = self.config.stop_sequences
            
            # Prepare safety settings
            safety_settings = self.config.safety_settings or {}
            
            # Create model WITHOUT tools (tools will be passed per request like original Gemini CLI)
            self._client = genai.GenerativeModel(
                model_name=self.config.model,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
        except Exception as e:
            raise classify_error(e)
    
    async def generate_content(
        self,
        messages: List[Message],
        config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None
    ) -> GenerateContentResponse:
        """Generate content using Gemini API."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages_to_gemini(messages)
            
            # Execute with retry logic
            response = await self.retry_manager.retry(
                lambda: self._generate_content_impl(gemini_messages, config, tools, system_instruction),
                model=self.config.model
            )
            
            return response
            
        except Exception as e:
            error = classify_error(e)
            logger.error(f"Error generating content: {error}")
            raise error
    
    async def generate_content_stream(
        self,
        messages: List[Message],
        config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Generate content with streaming response."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages_to_gemini(messages)
            
            # Execute streaming with retry logic
            async def stream_generator():
                async for chunk in self._generate_content_stream_impl(gemini_messages, config, tools, system_instruction):
                    yield chunk
            
            # Note: Retry logic for streaming is more complex and may need special handling
            async for chunk in stream_generator():
                yield chunk
                
        except Exception as e:
            error = classify_error(e)
            logger.error(f"Error in streaming generation: {error}")
            raise error
    
    async def count_tokens(self, messages: List[Message]) -> int:
        """Count tokens in the given messages."""
        if not self._initialized:
            await self.initialize()
        
        try:
            gemini_messages = self._convert_messages_to_gemini(messages)
            
            # Use the count_tokens method if available
            if hasattr(self._client, 'count_tokens'):
                result = await asyncio.to_thread(
                    self._client.count_tokens,
                    gemini_messages
                )
                return result.total_tokens
            else:
                # Fallback: estimate based on text content
                total_text = ""
                for message in messages:
                    total_text += message.get_text_content() + " "
                
                # Rough estimation: ~4 characters per token
                return len(total_text) // 4
                
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            return 0
    
    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming."""
        return True
    
    def get_context_limit(self) -> int:
        """Get the context window limit for this model."""
        # Common Gemini model limits
        context_limits = {
            "gemini-2.0-flash-exp": 1048576,  # 1M tokens
            "gemini-1.5-pro": 2097152,       # 2M tokens
            "gemini-1.5-flash": 1048576,     # 1M tokens
            "gemini-1.0-pro": 32768,         # 32K tokens
        }
        return context_limits.get(self.config.model, 32768)
    
    def set_tools(self, function_declarations: List[Dict[str, Any]]) -> None:
        """
        Set tools for this content generator.
        
        Args:
            function_declarations: List of function declarations in our standard format
        """
        if function_declarations:
            # Convert to Gemini's native tool format
            self.config.tools = convert_function_schemas_to_gemini_tools(function_declarations)
        else:
            self.config.tools = None
    
    def get_tools(self) -> Optional[List[Dict[str, Any]]]:
        """Get the currently configured tools."""
        return self.config.tools
    
    async def _generate_content_impl(
        self,
        gemini_messages: List[Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None
    ) -> GenerateContentResponse:
        """Internal implementation of content generation."""
        try:
            if not gemini_messages:
                return GenerateContentResponse()
            
            # Prepare generation config
            generation_config = {
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens
            }
            
            # Override with runtime config if provided
            if config:
                generation_config.update(config)
            
            # Prepare tools if available (matching original Gemini CLI pattern)
            effective_tools = None
            if tools is not None:
                # Tools are already in Gemini API format from format_tools_for_gemini_api()
                # Extract function declarations and convert to protobuf format
                function_declarations = []
                for tool_group in tools:
                    if isinstance(tool_group, dict) and "functionDeclarations" in tool_group:
                        function_declarations.extend(tool_group["functionDeclarations"])
                
                if function_declarations:
                    effective_tools = convert_function_schemas_to_gemini_tools(function_declarations)
                else:
                    # Fallback: assume tools are already function declarations
                    effective_tools = convert_function_schemas_to_gemini_tools(tools)
            elif self.config.tools:
                # Use config tools as fallback
                effective_tools = self.config.tools
            
            # For now, if system_instruction is provided, prepend it as a user message
            # This is a fallback until we can identify the correct Gemini Python API parameter
            final_messages = gemini_messages
            if system_instruction:
                system_message = {"role": "user", "parts": [{"text": system_instruction}]}
                final_messages = [system_message] + gemini_messages
            
            response = await asyncio.to_thread(
                self._client.generate_content,
                final_messages,
                generation_config=generation_config,
                tools=effective_tools
            )
            
            # Extract parts from the response (including function calls)
            parts = []
            if response.parts:
                for part in response.parts:
                    if hasattr(part, 'text') and part.text:
                        parts.append({"text": part.text})
                    elif hasattr(part, 'function_call') and part.function_call:
                        # Convert function call to dictionary format
                        function_call_dict = {
                            "name": part.function_call.name,
                            "args": {}
                        }
                        # Extract arguments from the function call
                        if hasattr(part.function_call, 'args') and part.function_call.args:
                            for key, value in part.function_call.args.items():
                                # Convert protobuf Value to Python types
                                if hasattr(value, 'string_value'):
                                    function_call_dict["args"][key] = value.string_value
                                elif hasattr(value, 'number_value'):
                                    function_call_dict["args"][key] = value.number_value
                                elif hasattr(value, 'bool_value'):
                                    function_call_dict["args"][key] = value.bool_value
                                else:
                                    # Fallback for other types
                                    function_call_dict["args"][key] = str(value)
                        
                        parts.append({"function_call": function_call_dict})
                        
            # Convert to our response format
            return GenerateContentResponse(
                candidates=[
                    GenerationCandidate(
                        content={
                            "role": "model",
                            "parts": parts
                        },
                        finish_reason=getattr(response.candidates[0], 'finish_reason', None) if response.candidates else None
                    )
                ],
                usage_metadata=UsageMetadata(
                    prompt_token_count=getattr(response.usage_metadata, 'prompt_token_count', 0) if hasattr(response, 'usage_metadata') else 0,
                    candidates_token_count=getattr(response.usage_metadata, 'candidates_token_count', 0) if hasattr(response, 'usage_metadata') else 0,
                    total_token_count=getattr(response.usage_metadata, 'total_token_count', 0) if hasattr(response, 'usage_metadata') else 0
                )
            )
            
        except Exception as e:
            raise classify_error(e)
    
    async def _generate_content_stream_impl(
        self,
        gemini_messages: List[Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Internal implementation of streaming content generation."""
        try:
            if not gemini_messages:
                return
            
            # Debug: Log gemini messages for debugging function response format
            import json
            logger.debug(f"🔍 Gemini messages being sent (streaming):")
            for i, msg in enumerate(gemini_messages):
                logger.debug(f"  Message {i+1}: {json.dumps(msg, indent=2)}")
            
            # Prepare generation config
            generation_config = {
                "temperature": self.config.temperature,
                "max_output_tokens": self.config.max_tokens
            }
            
            # Override with runtime config if provided
            if config:
                generation_config.update(config)
            
            # Prepare tools if available (matching original Gemini CLI pattern)
            effective_tools = None
            if tools is not None:
                # Tools are already in Gemini API format from format_tools_for_gemini_api()
                # Extract function declarations and convert to protobuf format
                function_declarations = []
                for tool_group in tools:
                    if isinstance(tool_group, dict) and "functionDeclarations" in tool_group:
                        function_declarations.extend(tool_group["functionDeclarations"])
                
                if function_declarations:
                    effective_tools = convert_function_schemas_to_gemini_tools(function_declarations)
                else:
                    # Fallback: assume tools are already function declarations
                    effective_tools = convert_function_schemas_to_gemini_tools(tools)
            elif self.config.tools:
                # Use config tools as fallback
                effective_tools = self.config.tools
            
            # Generate streaming response
            def _stream_generate():
                # For now, if system_instruction is provided, prepend it as a user message
                # This is a fallback until we can identify the correct Gemini Python API parameter
                final_messages = gemini_messages
                if system_instruction:
                    system_message = {"role": "user", "parts": [{"text": system_instruction}]}
                    final_messages = [system_message] + gemini_messages
                
                return self._client.generate_content(
                    final_messages,
                    generation_config=generation_config,
                    tools=effective_tools,
                    stream=True
                )
            
            stream = await asyncio.to_thread(_stream_generate)
            
            for chunk in stream:
                # Handle streaming chunks that can contain text OR function calls
                parts = []
                
                # Safely check for text content without triggering conversion errors
                try:
                    # Only access .text if the chunk doesn't have function calls
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                # Process each part individually
                                for part in candidate.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        parts.append({"text": part.text})
                                    elif hasattr(part, 'function_call') and part.function_call:
                                        # Convert function call to our format
                                        function_call_dict = {
                                            "name": part.function_call.name,
                                            "args": {}
                                        }
                                        # Extract arguments from the function call
                                        if hasattr(part.function_call, 'args') and part.function_call.args:
                                            for key, value in part.function_call.args.items():
                                                # Convert protobuf Value to Python types
                                                function_call_dict["args"][key] = value
                                        
                                        parts.append({"function_call": function_call_dict})
                    
                    # Fallback: try to get text only if no parts were found and no function calls
                    if not parts and hasattr(chunk, 'text'):
                        text_content = getattr(chunk, 'text', None)
                        if text_content:
                            parts.append({"text": text_content})
                            
                except Exception as e:
                    # If we get a function calling error, the chunk likely contains function calls
                    # Try to extract them directly from the chunk structure
                    logger.debug(f"Error accessing chunk content: {e}")
                    if hasattr(chunk, 'candidates') and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                for part in candidate.content.parts:
                                    if hasattr(part, 'function_call') and part.function_call:
                                        function_call_dict = {
                                            "name": part.function_call.name,
                                            "args": dict(part.function_call.args)
                                        }
                                        parts.append({"function_call": function_call_dict})
                
                # Only yield response if we have parts to return
                if parts:
                    yield GenerateContentResponse(
                        candidates=[
                            GenerationCandidate(
                                content={
                                    "role": "model",
                                    "parts": parts
                                }
                            )
                        ]
                    )
                                
        except Exception as e:
            raise classify_error(e)
    
    def _convert_messages_to_gemini(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert internal message format to Gemini API format."""
        gemini_messages = []
        
        for message in messages:
            gemini_message = {
                "role": message.role.value,
                "parts": []
            }
            
            for part in message.parts:
                gemini_part = {}
                
                if part.text:
                    gemini_part["text"] = part.text
                elif part.function_call:
                    gemini_part["function_call"] = part.function_call
                elif part.function_response:
                    gemini_part["function_response"] = part.function_response
                elif part.inline_data:
                    gemini_part["inline_data"] = part.inline_data
                elif part.file_data:
                    gemini_part["file_data"] = part.file_data
                
                if gemini_part:
                    gemini_message["parts"].append(gemini_part)
            
            if gemini_message["parts"]:
                gemini_messages.append(gemini_message)
        
        return gemini_messages
    
    def set_tools(self, tools: List[Dict[str, Any]]) -> None:
        """Set the available tools for function calling."""
        # Store tools in config for use in API calls (matching original Gemini CLI approach)
        if not tools:
            self.config.tools = None
        else:
            # Extract function schemas from the tools format and store for later use
            function_schemas = []
            for tool_group in tools:
                if "functionDeclarations" in tool_group:
                    function_schemas.extend(tool_group["functionDeclarations"])
            
            if function_schemas:
                # Convert JSON schemas to Gemini protobuf format and store
                gemini_tools = convert_function_schemas_to_gemini_tools(function_schemas)
                self.config.tools = gemini_tools
            else:
                self.config.tools = None


# Factory functions

def create_content_generator_config(
    model: str = "gemini-2.0-flash-exp",
    auth_type: AuthType = AuthType.API_KEY,
    api_key: Optional[str] = None,
    **kwargs
) -> GeminiProviderConfig:
    """Create a Gemini content generator configuration (backward compatibility)."""
    return GeminiProviderConfig(
        model=model,
        provider=ModelProvider.GEMINI,
        auth_type=auth_type,
        api_key=api_key,
        **kwargs
    )


def create_gemini_content_generator(
    model: str = "gemini-2.0-flash-exp",
    auth_type: AuthType = AuthType.API_KEY,
    api_key: Optional[str] = None,
    **kwargs
) -> GeminiContentGenerator:
    """Create a Gemini content generator with the given configuration."""
    config = GeminiProviderConfig(
        model=model,
        provider=ModelProvider.GEMINI,
        auth_type=auth_type,
        api_key=api_key,
        **kwargs
    )
    return GeminiContentGenerator(config)


def get_available_models() -> List[str]:
    """Get list of available Gemini models."""
    try:
        models = []
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                models.append(model.name)
        return models
    except Exception as e:
        logger.warning(f"Could not fetch available models: {e}")
        return [
            "gemini-2.0-flash-exp",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro"
        ]