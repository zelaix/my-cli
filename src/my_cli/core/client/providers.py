"""
Provider-agnostic interfaces and enums for AI model providers.

This module defines the core interfaces and types that allow the CLI to work
with multiple AI model providers (Gemini, Kimi, OpenAI, etc.) in a unified way.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from pathlib import Path

from pydantic import BaseModel, Field

from .turn import Message, MessageRole, MessagePart
from .errors import GeminiError


class ModelProvider(Enum):
    """Supported AI model providers."""
    GEMINI = "gemini"
    KIMI = "kimi"
    OPENAI = "openai"  # For future expansion
    ANTHROPIC = "anthropic"  # For future expansion


class AuthType(Enum):
    """Authentication types for API clients."""
    # Universal auth types
    API_KEY = "api_key"
    
    # Gemini-specific auth types
    OAUTH = "oauth"
    APPLICATION_DEFAULT_CREDENTIALS = "application_default_credentials"
    SERVICE_ACCOUNT = "service_account"
    VERTEX_AI = "vertex_ai"
    
    # Kimi-specific auth types (provider-based)
    KIMI_MOONSHOT = "kimi_moonshot"
    KIMI_DEEPINFRA = "kimi_deepinfra"
    KIMI_TOGETHER = "kimi_together"
    KIMI_FIREWORKS = "kimi_fireworks"
    KIMI_GROQ = "kimi_groq"
    KIMI_OPENROUTER = "kimi_openrouter"


@dataclass
class BaseProviderConfig:
    """Base configuration for any provider."""
    model: str
    provider: ModelProvider
    auth_type: AuthType
    
    # Common authentication credentials
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    
    # Generation parameters (will be mapped to provider-specific formats)
    temperature: float = 0.7
    max_tokens: int = 8192
    top_p: float = 0.95
    top_k: int = 40
    stop_sequences: Optional[List[str]] = None
    
    # Request settings
    timeout_seconds: float = 60.0
    retry_config: Optional[Any] = None  # Will be properly typed when importing
    
    # Streaming settings
    stream: bool = True
    stream_options: Optional[Dict[str, Any]] = None


@dataclass
class GeminiProviderConfig(BaseProviderConfig):
    """Gemini-specific configuration."""
    # Gemini-specific auth fields
    service_account_path: Optional[str] = None
    oauth_credentials: Optional[Dict[str, Any]] = None
    project_id: Optional[str] = None
    location: Optional[str] = None
    
    # Gemini-specific generation parameters
    safety_settings: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Set Gemini-specific defaults after initialization."""
        self.provider = ModelProvider.GEMINI


@dataclass  
class KimiProviderConfig(BaseProviderConfig):
    """Kimi-specific configuration."""
    # Kimi provider selection (affects base_url and auth)
    kimi_provider: str = "moonshot"  # moonshot, deepinfra, together, etc.
    
    # Provider-specific base URLs (auto-set based on kimi_provider)
    provider_urls: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        """Set provider-specific defaults after initialization."""
        self.provider = ModelProvider.KIMI
        
        if self.provider_urls is None:
            self.provider_urls = {
                "moonshot": "https://api.moonshot.cn/v1",
                "deepinfra": "https://api.deepinfra.com/v1/openai",
                "together": "https://api.together.xyz/v1",
                "fireworks": "https://api.fireworks.ai/inference/v1",
                "groq": "https://api.groq.com/openai/v1",
                "openrouter": "https://openrouter.ai/api/v1"
            }
        
        # Auto-set base_url if not provided
        if not self.base_url and self.kimi_provider in self.provider_urls:
            self.base_url = self.provider_urls[self.kimi_provider]
        
        # Auto-set auth_type based on provider
        if self.auth_type == AuthType.API_KEY:
            auth_type_map = {
                "moonshot": AuthType.KIMI_MOONSHOT,
                "deepinfra": AuthType.KIMI_DEEPINFRA,
                "together": AuthType.KIMI_TOGETHER,
                "fireworks": AuthType.KIMI_FIREWORKS,
                "groq": AuthType.KIMI_GROQ,
                "openrouter": AuthType.KIMI_OPENROUTER
            }
            if self.kimi_provider in auth_type_map:
                self.auth_type = auth_type_map[self.kimi_provider]


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
    """Provider-agnostic response from content generation."""
    candidates: List[GenerationCandidate] = Field(default_factory=list)
    usage_metadata: Optional[UsageMetadata] = None
    prompt_feedback: Optional[Dict[str, Any]] = None
    provider: Optional[ModelProvider] = None
    
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
    def tool_calls(self) -> List[Dict[str, Any]]:
        """Get any function calls from the response in OpenAI format."""
        tool_calls = []
        if self.candidates:
            candidate = self.candidates[0]
            content = candidate.content
            if content and "parts" in content:
                call_counter = 1
                for part in content["parts"]:
                    if isinstance(part, dict) and "function_call" in part:
                        func_call = part["function_call"]
                        # Convert Gemini format to OpenAI format expected by parser
                        openai_format = {
                            "id": f"call_{call_counter:03d}",
                            "function": {
                                "name": func_call.get("name", ""),
                                "arguments": json.dumps(func_call.get("args", {}))
                            }
                        }
                        tool_calls.append(openai_format)
                        call_counter += 1
        return tool_calls
    
    @property
    def function_calls(self) -> List[Dict[str, Any]]:
        """Get any function calls from the response in native Gemini format (matching original Gemini CLI)."""
        function_calls = []
        if self.candidates:
            candidate = self.candidates[0]
            content = candidate.content
            if content and "parts" in content:
                call_counter = 1
                for part in content["parts"]:
                    if isinstance(part, dict) and "function_call" in part:
                        func_call = part["function_call"]
                        # Preserve original ID if it exists, otherwise generate one (matching original Turn.ts pattern)
                        original_id = func_call.get("id")
                        generated_id = f"call_{call_counter:03d}"
                        
                        gemini_format = {
                            "id": original_id if original_id else generated_id,
                            "name": func_call.get("name", ""),
                            "args": func_call.get("args", {})
                        }
                        function_calls.append(gemini_format)
                        call_counter += 1
        return function_calls
    
    @property
    def has_content(self) -> bool:
        """Check if this response has any content (text or function calls)."""
        return bool(self.text or self.tool_calls)


class BaseContentGenerator(ABC):
    """Abstract base class for all content generators."""
    
    def __init__(self, config: BaseProviderConfig):
        self.config = config
        self._initialized = False
    
    @property
    def provider(self) -> ModelProvider:
        """Get the provider type."""
        return self.config.provider
    
    @property
    def model(self) -> str:
        """Get the model name."""
        return self.config.model
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the content generator."""
        pass
    
    @abstractmethod
    async def generate_content(
        self,
        messages: List[Message],
        config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> GenerateContentResponse:
        """Generate content based on messages."""
        pass
    
    @abstractmethod
    async def generate_content_stream(
        self,
        messages: List[Message],
        config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None
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
    
    @abstractmethod
    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming."""
        pass
    
    @abstractmethod
    def get_context_limit(self) -> int:
        """Get the context window limit for this model."""
        pass
    
    def set_tools(self, tools: List[Dict[str, Any]]) -> None:
        """Set the available tools for function calling."""
        if hasattr(self.config, 'tools'):
            self.config.tools = tools
        else:
            # For providers that don't support tools, this is a no-op
            pass


def detect_provider_from_model(model: str) -> ModelProvider:
    """Detect the provider based on model name."""
    model_lower = model.lower().strip()
    
    if model_lower.startswith("kimi-"):
        return ModelProvider.KIMI
    elif model_lower.startswith("gemini-") or model_lower in ["gemini-pro", "gemini-pro-vision", "text-bison", "chat-bison"]:
        return ModelProvider.GEMINI
    elif model_lower.startswith("gpt-") or model_lower.startswith("o1-"):
        return ModelProvider.OPENAI
    elif model_lower.startswith("claude-"):
        return ModelProvider.ANTHROPIC
    else:
        # Raise exception for unknown models instead of defaulting
        raise ValueError(f"Unknown model provider for model: {model}")


def get_provider_config_class(provider: ModelProvider) -> type:
    """Get the appropriate config class for a provider."""
    if provider == ModelProvider.GEMINI:
        return GeminiProviderConfig
    elif provider == ModelProvider.KIMI:
        return KimiProviderConfig
    else:
        return BaseProviderConfig


def create_provider_config(
    model: str,
    provider: Optional[ModelProvider] = None,
    **kwargs
) -> BaseProviderConfig:
    """Create a provider configuration based on model name."""
    if provider is None:
        provider = detect_provider_from_model(model)
    
    config_class = get_provider_config_class(provider)
    return config_class(model=model, provider=provider, **kwargs)