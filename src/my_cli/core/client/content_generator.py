"""
Enhanced content generator for My CLI with comprehensive authentication support.

This module provides sophisticated content generation with multiple authentication
methods, streaming support, and integration with the original Gemini CLI patterns.
"""

import asyncio
import logging
import os
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from pathlib import Path

from pydantic import BaseModel, Field
import google.generativeai as genai
from google.oauth2 import service_account
from google.auth import default

from .errors import (
    GeminiError,
    AuthenticationError,
    ConfigurationError,
    classify_error,
)
from .retry import RetryManager, RetryConfig
from .turn import Message, MessageRole, MessagePart, Turn

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """Authentication types for API clients."""
    API_KEY = "api_key"
    OAUTH = "oauth"
    APPLICATION_DEFAULT_CREDENTIALS = "application_default_credentials"
    SERVICE_ACCOUNT = "service_account"
    VERTEX_AI = "vertex_ai"


@dataclass
class ContentGeneratorConfig:
    """Configuration for content generation."""
    model: str
    auth_type: AuthType
    
    # Authentication credentials
    api_key: Optional[str] = None
    service_account_path: Optional[str] = None
    oauth_credentials: Optional[Dict[str, Any]] = None
    project_id: Optional[str] = None
    location: Optional[str] = None
    
    # Generation parameters
    temperature: float = 0.7
    max_tokens: int = 8192
    top_p: float = 0.95
    top_k: int = 40
    stop_sequences: Optional[List[str]] = None
    
    # Safety settings
    safety_settings: Optional[Dict[str, Any]] = None
    
    # Tools and function calling
    tools: Optional[List[Dict[str, Any]]] = None
    tool_config: Optional[Dict[str, Any]] = None
    
    # Request settings
    timeout_seconds: float = 60.0
    retry_config: Optional[RetryConfig] = None
    
    # Streaming settings
    stream: bool = True
    stream_options: Optional[Dict[str, Any]] = None


class GenerationCandidate(BaseModel):
    """A candidate response from content generation."""
    content: Dict[str, Any] = Field(description="Generated content")
    finish_reason: Optional[Any] = Field(default=None, description="Reason generation finished")
    safety_ratings: Optional[List[Dict[str, Any]]] = Field(default=None, description="Safety ratings")
    citation_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Citation information")


class UsageMetadata(BaseModel):
    """Token usage metadata from generation."""
    prompt_token_count: int = Field(default=0, description="Tokens in the prompt")
    candidates_token_count: int = Field(default=0, description="Tokens in candidates")
    total_token_count: int = Field(default=0, description="Total tokens used")
    cached_content_token_count: Optional[int] = Field(default=None, description="Cached tokens")


class GenerateContentResponse(BaseModel):
    """Response from content generation."""
    candidates: List[GenerationCandidate] = Field(default_factory=list)
    usage_metadata: Optional[UsageMetadata] = None
    prompt_feedback: Optional[Dict[str, Any]] = None
    
    @property
    def text(self) -> str:
        """Get the text content from the first candidate."""
        if self.candidates:
            candidate = self.candidates[0]
            content = candidate.content
            if content and "parts" in content:
                text_parts = []
                for part in content["parts"]:
                    if isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                return "".join(text_parts)
        return ""
    
    @property
    def has_content(self) -> bool:
        """Check if response has actual content."""
        return bool(self.text.strip())


class ContentGenerator(ABC):
    """Abstract base class for content generators."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the content generator."""
        pass
    
    @abstractmethod
    async def generate_content(
        self,
        messages: List[Message],
        config: Optional[Dict[str, Any]] = None
    ) -> GenerateContentResponse:
        """Generate content based on messages."""
        pass
    
    @abstractmethod
    async def generate_content_stream(
        self,
        messages: List[Message],
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Generate content with streaming response."""
        pass
    
    @abstractmethod
    async def count_tokens(
        self,
        messages: List[Message]
    ) -> int:
        """Count tokens in the given messages."""
        pass


class GeminiContentGenerator(ContentGenerator):
    """Enhanced content generator for Google Gemini API."""
    
    def __init__(self, config: ContentGeneratorConfig):
        self.config = config
        self._client: Optional[genai.GenerativeModel] = None
        self._chat_session: Optional[Any] = None
        self._initialized = False
        
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
            
            # Create model
            self._client = genai.GenerativeModel(
                model_name=self.config.model,
                generation_config=generation_config,
                safety_settings=safety_settings,
                tools=self.config.tools,
                tool_config=self.config.tool_config
            )
            
        except Exception as e:
            raise classify_error(e)
    
    async def generate_content(
        self,
        messages: List[Message],
        config: Optional[Dict[str, Any]] = None
    ) -> GenerateContentResponse:
        """Generate content using Gemini API."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages_to_gemini(messages)
            
            # Execute with retry logic
            response = await self.retry_manager.retry(
                lambda: self._generate_content_impl(gemini_messages, config),
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
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Generate content with streaming response."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Convert messages to Gemini format
            gemini_messages = self._convert_messages_to_gemini(messages)
            
            # Execute streaming with retry logic
            async def stream_generator():
                async for chunk in self._generate_content_stream_impl(gemini_messages, config):
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
    
    async def _generate_content_impl(
        self,
        gemini_messages: List[Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None
    ) -> GenerateContentResponse:
        """Internal implementation of content generation."""
        try:
            # For now, handle simple text generation
            if gemini_messages:
                # Extract text from the last user message
                last_message = gemini_messages[-1]
                if last_message.get("role") == "user" and "parts" in last_message:
                    text_parts = []
                    for part in last_message["parts"]:
                        if isinstance(part, dict) and "text" in part:
                            text_parts.append(part["text"])
                    
                    if text_parts:
                        prompt = " ".join(text_parts)
                        
                        # Generate response
                        response = await asyncio.to_thread(
                            self._client.generate_content,
                            prompt
                        )
                        
                        # Convert to our response format
                        return GenerateContentResponse(
                            candidates=[
                                GenerationCandidate(
                                    content={
                                        "role": "model",
                                        "parts": [{"text": response.text}]
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
            
            return GenerateContentResponse()
            
        except Exception as e:
            raise classify_error(e)
    
    async def _generate_content_stream_impl(
        self,
        gemini_messages: List[Dict[str, Any]],
        config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Internal implementation of streaming content generation."""
        try:
            if gemini_messages:
                # Extract text from the last user message
                last_message = gemini_messages[-1]
                if last_message.get("role") == "user" and "parts" in last_message:
                    text_parts = []
                    for part in last_message["parts"]:
                        if isinstance(part, dict) and "text" in part:
                            text_parts.append(part["text"])
                    
                    if text_parts:
                        prompt = " ".join(text_parts)
                        
                        # Generate streaming response
                        def _stream_generate():
                            return self._client.generate_content(prompt, stream=True)
                        
                        stream = await asyncio.to_thread(_stream_generate)
                        
                        for chunk in stream:
                            if chunk.text:
                                yield GenerateContentResponse(
                                    candidates=[
                                        GenerationCandidate(
                                            content={
                                                "role": "model",
                                                "parts": [{"text": chunk.text}]
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


# Factory functions

def create_content_generator_config(
    model: str = "gemini-2.0-flash-exp",
    auth_type: AuthType = AuthType.API_KEY,
    api_key: Optional[str] = None,
    **kwargs
) -> ContentGeneratorConfig:
    """Create a content generator configuration."""
    return ContentGeneratorConfig(
        model=model,
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
    config = create_content_generator_config(
        model=model,
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