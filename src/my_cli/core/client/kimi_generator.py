"""
Kimi K2 content generator for My CLI.

This module provides content generation support for the Kimi K2 model series
through various API providers (Moonshot, DeepInfra, Together AI, etc.) using
OpenAI-compatible API endpoints.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from pydantic import BaseModel

from .providers import (
    BaseContentGenerator,
    KimiProviderConfig,
    GenerateContentResponse,
    GenerationCandidate,
    UsageMetadata,
    ModelProvider
)
from .turn import Message, MessageRole, MessagePart
from .errors import (
    GeminiError,
    AuthenticationError,
    ConfigurationError,
    classify_error,
)
from .retry import RetryManager, RetryConfig

logger = logging.getLogger(__name__)


class OpenAIMessage(BaseModel):
    """OpenAI-compatible message format."""
    role: str
    content: str


class OpenAIRequest(BaseModel):
    """OpenAI-compatible request format."""
    model: str
    messages: List[OpenAIMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[List[str]] = None
    stream: bool = False


class OpenAIChoice(BaseModel):
    """OpenAI-compatible choice format."""
    index: int
    message: Optional[OpenAIMessage] = None
    delta: Optional[Dict[str, Any]] = None
    finish_reason: Optional[str] = None


class OpenAIUsage(BaseModel):
    """OpenAI-compatible usage format."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class OpenAIResponse(BaseModel):
    """OpenAI-compatible response format."""
    id: str
    object: str
    created: int
    model: str
    choices: List[OpenAIChoice]
    usage: Optional[OpenAIUsage] = None


class KimiContentGenerator(BaseContentGenerator):
    """Content generator for Kimi K2 models using OpenAI-compatible API."""
    
    def __init__(self, config: KimiProviderConfig):
        super().__init__(config)
        self.config: KimiProviderConfig = config
        self._client: Optional[httpx.AsyncClient] = None
        
        # Initialize retry manager
        self.retry_manager = RetryManager(RetryConfig())
        
        # Model capabilities
        self._context_limits = {
            "kimi-k2-instruct": 128000,
            "kimi-k2-base": 128000,
        }
    
    async def initialize(self) -> None:
        """Initialize the Kimi client with authentication."""
        if self._initialized:
            return
        
        try:
            await self._configure_authentication()
            await self._create_client()
            self._initialized = True
            logger.info(
                f"Initialized Kimi content generator with model {self.config.model} "
                f"via {self.config.kimi_provider}"
            )
            
        except Exception as e:
            error = classify_error(e)
            logger.error(f"Failed to initialize Kimi content generator: {error}")
            raise error
    
    async def _configure_authentication(self) -> None:
        """Configure authentication for the selected Kimi provider."""
        if not self.config.api_key:
            # Try to get from environment based on provider
            import os
            env_var_map = {
                "moonshot": "KIMI_MOONSHOT_API_KEY",
                "deepinfra": "DEEPINFRA_TOKEN",
                "together": "TOGETHER_API_KEY",
                "fireworks": "FIREWORKS_API_KEY",
                "groq": "GROQ_API_KEY",
                "openrouter": "OPENROUTER_API_KEY"
            }
            
            # Try provider-specific env var first, then generic
            env_vars = [
                env_var_map.get(self.config.kimi_provider),
                "MY_CLI_KIMI_API_KEY",
                "KIMI_API_KEY"
            ]
            
            for env_var in env_vars:
                if env_var:
                    api_key = os.getenv(env_var)
                    if api_key:
                        self.config.api_key = api_key
                        break
            
            if not self.config.api_key:
                raise AuthenticationError(
                    f"API key is required for Kimi {self.config.kimi_provider} provider. "
                    f"Set {env_var_map.get(self.config.kimi_provider, 'MY_CLI_KIMI_API_KEY')} environment variable.",
                    auth_type=self.config.auth_type.value
                )
    
    async def _create_client(self) -> None:
        """Create the HTTP client with proper headers."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "my-cli/0.1.0"
        }
        
        # Set authorization header based on provider
        if self.config.kimi_provider in ["moonshot", "deepinfra", "together", "fireworks", "groq"]:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        elif self.config.kimi_provider == "openrouter":
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            headers["HTTP-Referer"] = "https://my-cli.dev"  # Required by OpenRouter
            headers["X-Title"] = "My CLI"
        
        timeout = httpx.Timeout(self.config.timeout_seconds)
        
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=headers,
            timeout=timeout
        )
    
    async def generate_content(
        self,
        messages: List[Message],
        config: Optional[Dict[str, Any]] = None
    ) -> GenerateContentResponse:
        """Generate content using Kimi API."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Convert messages to OpenAI format
            openai_messages = self._convert_messages_to_openai(messages)
            
            # Create request
            request = self._create_request(openai_messages, stream=False, config=config)
            
            # Execute with retry logic
            response = await self.retry_manager.retry(
                lambda: self._generate_content_impl(request),
                model=self.config.model
            )
            
            return response
            
        except Exception as e:
            error = classify_error(e)
            logger.error(f"Error generating content with Kimi: {error}")
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
            # Convert messages to OpenAI format
            openai_messages = self._convert_messages_to_openai(messages)
            
            # Create streaming request
            request = self._create_request(openai_messages, stream=True, config=config)
            
            # Execute streaming request
            async for chunk in self._generate_content_stream_impl(request):
                yield chunk
                
        except Exception as e:
            error = classify_error(e)
            logger.error(f"Error in streaming generation with Kimi: {error}")
            raise error
    
    async def count_tokens(self, messages: List[Message]) -> int:
        """Count tokens in the given messages."""
        # Kimi K2 uses tiktoken-like counting, but we'll use a simple estimation
        total_text = ""
        for message in messages:
            total_text += message.get_text_content() + " "
        
        # Rough estimation: ~4 characters per token (similar to GPT tokenization)
        return len(total_text) // 4
    
    def supports_streaming(self) -> bool:
        """Check if this provider supports streaming."""
        return True
    
    def get_context_limit(self) -> int:
        """Get the context window limit for this model."""
        return self._context_limits.get(self.config.model, 128000)
    
    async def _generate_content_impl(self, request: OpenAIRequest) -> GenerateContentResponse:
        """Internal implementation of content generation."""
        try:
            response = await self._client.post(
                "/chat/completions",
                json=request.model_dump(exclude_none=True)
            )
            response.raise_for_status()
            
            openai_response = OpenAIResponse(**response.json())
            return self._convert_openai_to_internal(openai_response)
            
        except httpx.HTTPStatusError as e:
            raise self._map_http_error(e)
        except Exception as e:
            raise classify_error(e)
    
    async def _generate_content_stream_impl(
        self, 
        request: OpenAIRequest
    ) -> AsyncGenerator[GenerateContentResponse, None]:
        """Internal implementation of streaming content generation."""
        try:
            async with self._client.stream(
                "POST",
                "/chat/completions",
                json=request.model_dump(exclude_none=True)
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        
                        if data.strip() == "[DONE]":
                            break
                        
                        try:
                            chunk_data = json.loads(data)
                            chunk = self._convert_openai_chunk_to_internal(chunk_data)
                            if chunk.has_content:
                                yield chunk
                        except json.JSONDecodeError:
                            continue
                            
        except httpx.HTTPStatusError as e:
            raise self._map_http_error(e)
        except Exception as e:
            raise classify_error(e)
    
    def _convert_messages_to_openai(self, messages: List[Message]) -> List[OpenAIMessage]:
        """Convert internal message format to OpenAI format."""
        openai_messages = []
        
        for message in messages:
            # Map roles
            role_map = {
                MessageRole.USER: "user",
                MessageRole.MODEL: "assistant",
                MessageRole.SYSTEM: "system"
            }
            
            role = role_map.get(message.role, "user")
            content = message.get_text_content()
            
            if content.strip():
                openai_messages.append(OpenAIMessage(role=role, content=content))
        
        return openai_messages
    
    def _get_api_model_name(self, model: str, provider: str) -> str:
        """Map internal model names to provider-specific API model names."""
        # Model name mappings for different providers
        model_mappings = {
            "moonshot": {
                "kimi-k2-instruct": "moonshot-v1-128k",  # Try common Moonshot model
                "kimi-k2-base": "moonshot-v1-32k",
            },
            "deepinfra": {
                "kimi-k2-instruct": "moonshotai/Kimi-K2-Instruct",
                "kimi-k2-base": "moonshotai/Kimi-K2-Base",
            },
            "together": {
                "kimi-k2-instruct": "moonshotai/Kimi-K2-Instruct", 
                "kimi-k2-base": "moonshotai/Kimi-K2-Base",
            },
            "groq": {
                "kimi-k2-instruct": "moonshotai/kimi-k2-instruct",
                "kimi-k2-base": "moonshotai/kimi-k2-base",
            },
            "fireworks": {
                "kimi-k2-instruct": "accounts/fireworks/models/kimi-k2-instruct",
                "kimi-k2-base": "accounts/fireworks/models/kimi-k2-base",
            },
            "openrouter": {
                "kimi-k2-instruct": "moonshotai/kimi-k2-instruct",
                "kimi-k2-base": "moonshotai/kimi-k2-base",
            }
        }
        
        provider_mapping = model_mappings.get(provider, {})
        return provider_mapping.get(model, model)  # Return original if no mapping found
    
    def _create_request(
        self,
        messages: List[OpenAIMessage],
        stream: bool = False,
        config: Optional[Dict[str, Any]] = None
    ) -> OpenAIRequest:
        """Create an OpenAI-compatible request."""
        # Map internal model name to provider-specific name
        api_model = self._get_api_model_name(self.config.model, self.config.kimi_provider)
        
        request = OpenAIRequest(
            model=api_model,
            messages=messages,
            stream=stream,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            top_p=self.config.top_p,
            stop=self.config.stop_sequences
        )
        
        # Apply any config overrides
        if config:
            for key, value in config.items():
                if hasattr(request, key):
                    setattr(request, key, value)
        
        return request
    
    def _convert_openai_to_internal(self, openai_response: OpenAIResponse) -> GenerateContentResponse:
        """Convert OpenAI response to internal format."""
        candidates = []
        
        for choice in openai_response.choices:
            if choice.message and choice.message.content:
                candidate = GenerationCandidate(
                    content={
                        "role": "model",
                        "parts": [{"text": choice.message.content}]
                    },
                    finish_reason=choice.finish_reason
                )
                candidates.append(candidate)
        
        usage_metadata = None
        if openai_response.usage:
            usage_metadata = UsageMetadata(
                prompt_token_count=openai_response.usage.prompt_tokens,
                candidates_token_count=openai_response.usage.completion_tokens,
                total_token_count=openai_response.usage.total_tokens
            )
        
        return GenerateContentResponse(
            candidates=candidates,
            usage_metadata=usage_metadata,
            provider=ModelProvider.KIMI
        )
    
    def _convert_openai_chunk_to_internal(self, chunk_data: Dict[str, Any]) -> GenerateContentResponse:
        """Convert OpenAI streaming chunk to internal format."""
        candidates = []
        
        if "choices" in chunk_data:
            for choice in chunk_data["choices"]:
                if "delta" in choice and "content" in choice["delta"]:
                    content_text = choice["delta"]["content"]
                    if content_text:
                        candidate = GenerationCandidate(
                            content={
                                "role": "model",
                                "parts": [{"text": content_text}]
                            },
                            finish_reason=choice.get("finish_reason")
                        )
                        candidates.append(candidate)
        
        return GenerateContentResponse(
            candidates=candidates,
            provider=ModelProvider.KIMI
        )
    
    def _map_http_error(self, error: httpx.HTTPStatusError) -> Exception:
        """Map HTTP errors to appropriate exception types."""
        status_code = error.response.status_code
        
        if status_code == 401:
            return AuthenticationError(
                f"Authentication failed for Kimi {self.config.kimi_provider} provider",
                auth_type=self.config.auth_type.value
            )
        elif status_code == 403:
            return AuthenticationError(
                f"Access forbidden for Kimi {self.config.kimi_provider} provider",
                auth_type=self.config.auth_type.value
            )
        elif status_code == 429:
            return GeminiError(f"Rate limit exceeded for Kimi {self.config.kimi_provider} provider")
        else:
            return GeminiError(f"HTTP {status_code} error from Kimi {self.config.kimi_provider}: {error.response.text}")


# Factory functions

def create_kimi_content_generator(
    model: str = "kimi-k2-instruct",
    kimi_provider: str = "moonshot",
    api_key: Optional[str] = None,
    **kwargs
) -> KimiContentGenerator:
    """Create a Kimi content generator with the given configuration."""
    config = KimiProviderConfig(
        model=model,
        kimi_provider=kimi_provider,
        api_key=api_key,
        **kwargs
    )
    return KimiContentGenerator(config)


def get_available_kimi_models() -> List[str]:
    """Get list of available Kimi models."""
    return [
        "kimi-k2-instruct",
        "kimi-k2-base"
    ]


def get_available_kimi_providers() -> List[str]:
    """Get list of available Kimi API providers."""
    return [
        "moonshot",
        "deepinfra", 
        "together",
        "fireworks",
        "groq",
        "openrouter"
    ]