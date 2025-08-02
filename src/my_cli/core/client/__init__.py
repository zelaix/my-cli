"""
Enhanced API client system for My CLI.

This package provides the complete API client implementation including
streaming, authentication, retry logic, and conversation management.
"""

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
    ContentGeneratorConfig,
    AuthType,
    GenerateContentResponse,
    create_gemini_content_generator,
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

__all__ = [
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
    "ContentGeneratorConfig",
    "AuthType",
    "GenerateContentResponse",
    "create_gemini_content_generator",
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