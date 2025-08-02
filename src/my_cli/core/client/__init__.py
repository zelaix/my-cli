"""
Enhanced API client system for My CLI with multi-provider support.

This package provides the complete API client implementation including
streaming, authentication, retry logic, and conversation management
for multiple AI providers (Gemini, Kimi K2, etc.).
"""

from typing import Optional

from .providers import (
    ModelProvider,
    AuthType,
    BaseProviderConfig,
    GeminiProviderConfig,
    KimiProviderConfig,
    GenerateContentResponse,
    GenerationCandidate,
    UsageMetadata,
    BaseContentGenerator,
    detect_provider_from_model,
    create_provider_config,
)
from .provider_factory import (
    create_content_generator,
    create_gemini_generator,
    create_kimi_generator,
    get_supported_providers,
    get_available_models,
    is_model_supported,
    get_model_provider,
)
from .streaming import (
    StreamEvent,
    GeminiStreamEvent,
    ContentStreamEvent,
    ErrorStreamEvent,
    FinishedStreamEvent,
    StreamingManager,
    create_content_event,
    create_error_event,
    create_finished_event,
)
from .content_generator import (
    ContentGenerator,
    GeminiContentGenerator,
    create_gemini_content_generator,
)
# Backward compatibility import will be added after the other imports
from .kimi_generator import (
    KimiContentGenerator,
    create_kimi_content_generator,
    get_available_kimi_models,
    get_available_kimi_providers,
)
from .gemini_client import (
    GeminiClient,
    GeminiClientConfig,
    ConversationSession,
    create_gemini_client,
)
from .turn import (
    Turn,
    TurnManager,
    TurnContext,
    TurnState,
    Message,
    MessageRole,
    create_turn_context,
)
from .errors import (
    GeminiError,
    AuthenticationError,
    AuthorizationError,
    QuotaExceededError,
    RetryableError,
    classify_error,
    create_user_friendly_message,
)
from .retry import (
    RetryManager,
    RetryConfig,
    RetryStats,
    retry_with_backoff,
)
from .token_manager import (
    TokenManager,
    TokenCounter,
    ConversationCompressor,
    CompressionStrategy,
    TokenLimits,
    create_token_manager,
)

# Backward compatibility aliases
ContentGeneratorConfig = GeminiProviderConfig

def create_api_client(
    api_key: Optional[str] = None,
    model: str = "gemini-2.0-flash-exp",
    auth_type: AuthType = AuthType.API_KEY,
    **kwargs
):
    """Create an API client with the given configuration (backward compatibility)."""
    from .provider_factory import create_content_generator
    return create_content_generator(model=model, api_key=api_key, auth_type=auth_type, **kwargs)

__all__ = [
    # Provider System
    "ModelProvider",
    "AuthType",
    "BaseProviderConfig",
    "GeminiProviderConfig", 
    "KimiProviderConfig",
    "GenerateContentResponse",
    "GenerationCandidate",
    "UsageMetadata",
    "BaseContentGenerator",
    "detect_provider_from_model",
    "create_provider_config",
    # Provider Factory
    "create_content_generator",
    "create_gemini_generator",
    "create_kimi_generator",
    "get_supported_providers",
    "get_available_models",
    "is_model_supported",
    "get_model_provider",
    # Streaming
    "StreamEvent",
    "GeminiStreamEvent", 
    "ContentStreamEvent",
    "ErrorStreamEvent",
    "FinishedStreamEvent",
    "StreamingManager",
    "create_content_event",
    "create_error_event",
    "create_finished_event",
    # Content Generation
    "ContentGenerator",
    "GeminiContentGenerator",
    "create_gemini_content_generator",
    "ContentGeneratorConfig",  # Backward compatibility
    "create_api_client",  # Backward compatibility
    # Kimi Generation
    "KimiContentGenerator",
    "create_kimi_content_generator",
    "get_available_kimi_models",
    "get_available_kimi_providers",
    # Main Client
    "GeminiClient",
    "GeminiClientConfig",
    "ConversationSession",
    "create_gemini_client",
    # Turn Management
    "Turn",
    "TurnManager",
    "TurnContext",
    "TurnState",
    "Message",
    "MessageRole",
    "create_turn_context",
    # Errors
    "GeminiError",
    "AuthenticationError",
    "AuthorizationError", 
    "QuotaExceededError",
    "RetryableError",
    "classify_error",
    "create_user_friendly_message",
    # Retry Logic
    "RetryManager",
    "RetryConfig",
    "RetryStats",
    "retry_with_backoff",
    # Token Management
    "TokenManager",
    "TokenCounter",
    "ConversationCompressor",
    "CompressionStrategy",
    "TokenLimits",
    "create_token_manager",
]