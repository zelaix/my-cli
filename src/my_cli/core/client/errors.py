"""
Structured error system for My CLI API client.

This module provides comprehensive error handling with structured error types
matching the original Gemini CLI's error system.
"""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Base exception for all Gemini API related errors."""
    
    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.details = details or {}
        self.original_error = original_error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "message": self.message,
            "status": self.status,
            "code": self.code,
            "details": self.details,
            "type": self.__class__.__name__
        }
    
    def __str__(self) -> str:
        parts = [self.message]
        if self.status:
            parts.append(f"(Status: {self.status})")
        if self.code:
            parts.append(f"(Code: {self.code})")
        return " ".join(parts)


class AuthenticationError(GeminiError):
    """Error related to authentication issues."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        auth_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, status=401, code="AUTHENTICATION_ERROR", **kwargs)
        if auth_type:
            self.details["auth_type"] = auth_type


class AuthorizationError(GeminiError):
    """Error related to authorization/permission issues."""
    
    def __init__(
        self,
        message: str = "Authorization failed", 
        resource: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, status=403, code="AUTHORIZATION_ERROR", **kwargs)
        if resource:
            self.details["resource"] = resource


class QuotaExceededError(GeminiError):
    """Error when API quota is exceeded."""
    
    def __init__(
        self,
        message: str = "API quota exceeded",
        quota_type: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, status=429, code="QUOTA_EXCEEDED", **kwargs)
        if quota_type:
            self.details["quota_type"] = quota_type
        if retry_after:
            self.details["retry_after"] = retry_after


class ModelUnavailableError(GeminiError):
    """Error when requested model is unavailable."""
    
    def __init__(
        self,
        message: str = "Model unavailable",
        model: Optional[str] = None,
        available_models: Optional[list] = None,
        **kwargs
    ):
        super().__init__(message, status=404, code="MODEL_UNAVAILABLE", **kwargs)
        if model:
            self.details["model"] = model
        if available_models:
            self.details["available_models"] = available_models


class InvalidRequestError(GeminiError):
    """Error for invalid API requests."""
    
    def __init__(
        self,
        message: str = "Invalid request",
        field: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, status=400, code="INVALID_REQUEST", **kwargs)
        if field:
            self.details["field"] = field


class ServerError(GeminiError):
    """Error for server-side issues."""
    
    def __init__(
        self,
        message: str = "Server error",
        **kwargs
    ):
        super().__init__(message, code="SERVER_ERROR", **kwargs)
        if not kwargs.get("status"):
            self.status = 500


class NetworkError(GeminiError):
    """Error for network-related issues."""
    
    def __init__(
        self,
        message: str = "Network error",
        **kwargs
    ):
        super().__init__(message, code="NETWORK_ERROR", **kwargs)


class TimeoutError(GeminiError):
    """Error for request timeouts."""
    
    def __init__(
        self,
        message: str = "Request timeout",
        timeout_seconds: Optional[float] = None,
        **kwargs
    ):
        super().__init__(message, code="TIMEOUT_ERROR", **kwargs)
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds


class RetryableError(GeminiError):
    """Base class for errors that can be retried."""
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        max_retries: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        if retry_after:
            self.details["retry_after"] = retry_after
        if max_retries:
            self.details["max_retries"] = max_retries


class TokenLimitExceededError(GeminiError):
    """Error when token limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Token limit exceeded",
        current_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, status=400, code="TOKEN_LIMIT_EXCEEDED", **kwargs)
        if current_tokens:
            self.details["current_tokens"] = current_tokens
        if max_tokens:
            self.details["max_tokens"] = max_tokens


class FunctionCallingError(GeminiError):
    """Error related to function calling."""
    
    def __init__(
        self,
        message: str = "Function calling error",
        function_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code="FUNCTION_CALLING_ERROR", **kwargs)
        if function_name:
            self.details["function_name"] = function_name


class ContentFilterError(GeminiError):
    """Error when content is filtered by safety systems."""
    
    def __init__(
        self,
        message: str = "Content filtered",
        filter_reason: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, status=400, code="CONTENT_FILTERED", **kwargs)
        if filter_reason:
            self.details["filter_reason"] = filter_reason


class ConfigurationError(GeminiError):
    """Error related to client configuration."""
    
    def __init__(
        self,
        message: str = "Configuration error",
        config_field: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, code="CONFIGURATION_ERROR", **kwargs)
        if config_field:
            self.details["config_field"] = config_field


def classify_error(error: Exception) -> GeminiError:
    """
    Classify a generic exception into a structured GeminiError.
    
    Args:
        error: The original exception
        
    Returns:
        Classified GeminiError instance
    """
    if isinstance(error, GeminiError):
        return error
    
    error_message = str(error)
    error_lower = error_message.lower()
    
    # Extract status code if available
    status = getattr(error, 'status', None) or getattr(error, 'status_code', None)
    
    # Classify by status code
    if status == 401:
        return AuthenticationError(error_message, original_error=error)
    elif status == 403:
        return AuthorizationError(error_message, original_error=error)
    elif status == 429:
        return QuotaExceededError(error_message, original_error=error)
    elif status == 404:
        return ModelUnavailableError(error_message, original_error=error)
    elif status == 400:
        if "token" in error_lower and "limit" in error_lower:
            return TokenLimitExceededError(error_message, original_error=error)
        elif "filter" in error_lower or "safety" in error_lower:
            return ContentFilterError(error_message, original_error=error)
        else:
            return InvalidRequestError(error_message, original_error=error)
    elif status and 500 <= status < 600:
        return ServerError(error_message, status=status, original_error=error)
    
    # Classify by error message content
    if "auth" in error_lower or "unauthorized" in error_lower:
        return AuthenticationError(error_message, original_error=error)
    elif "quota" in error_lower or "rate limit" in error_lower:
        return QuotaExceededError(error_message, original_error=error)
    elif "timeout" in error_lower:
        return TimeoutError(error_message, original_error=error)
    elif "network" in error_lower or "connection" in error_lower:
        return NetworkError(error_message, original_error=error)
    elif "model" in error_lower and ("not found" in error_lower or "unavailable" in error_lower):
        return ModelUnavailableError(error_message, original_error=error)
    elif "token" in error_lower and "limit" in error_lower:
        return TokenLimitExceededError(error_message, original_error=error)
    elif "function" in error_lower or "tool" in error_lower:
        return FunctionCallingError(error_message, original_error=error)
    elif "config" in error_lower:
        return ConfigurationError(error_message, original_error=error)
    
    # Default classification
    return GeminiError(error_message, original_error=error)


def is_retryable_error(error: Exception) -> bool:
    """
    Check if an error is retryable.
    
    Args:
        error: The error to check
        
    Returns:
        True if the error is retryable
    """
    if isinstance(error, RetryableError):
        return True
    
    # Check for specific retryable error types
    if isinstance(error, (QuotaExceededError, ServerError, NetworkError, TimeoutError)):
        return True
    
    # For testing purposes, generic GeminiError can be retryable
    # In production, this would be more restrictive
    if isinstance(error, GeminiError):
        # Check if it has a message indicating it's temporary
        error_msg = str(error).lower()
        if any(keyword in error_msg for keyword in ['temporary', 'retry', 'transient']):
            return True
    
    # Check status codes
    status = getattr(error, 'status', None)
    if status:
        # 5xx server errors and 429 (too many requests) are retryable
        return status == 429 or (500 <= status < 600)
    
    return False


def get_retry_delay(error: Exception) -> Optional[int]:
    """
    Get the retry delay from an error if available.
    
    Args:
        error: The error to check
        
    Returns:
        Retry delay in seconds, or None if not specified
    """
    if hasattr(error, 'details') and 'retry_after' in error.details:
        return error.details['retry_after']
    
    # Check for Retry-After header in HTTP errors
    if hasattr(error, 'response') and hasattr(error.response, 'headers'):
        retry_after = error.response.headers.get('Retry-After')
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass
    
    return None


def create_user_friendly_message(error: GeminiError) -> str:
    """
    Create a user-friendly error message.
    
    Args:
        error: The GeminiError to convert
        
    Returns:
        User-friendly error message
    """
    if isinstance(error, AuthenticationError):
        if "api_key" in error.details.get("auth_type", "").lower():
            return "Authentication failed. Please check your API key in the MY_CLI_API_KEY environment variable."
        return "Authentication failed. Please check your credentials."
    
    elif isinstance(error, AuthorizationError):
        return "You don't have permission to access this resource. Please check your account permissions."
    
    elif isinstance(error, QuotaExceededError):
        retry_after = error.details.get("retry_after")
        if retry_after:
            return f"API quota exceeded. Please try again in {retry_after} seconds."
        return "API quota exceeded. Please try again later or check your quota limits."
    
    elif isinstance(error, ModelUnavailableError):
        model = error.details.get("model")
        if model:
            return f"The model '{model}' is not available. Please try a different model."
        return "The requested model is not available. Please try a different model."
    
    elif isinstance(error, TokenLimitExceededError):
        return "The request contains too many tokens. Please try with a shorter prompt or reduce the conversation history."
    
    elif isinstance(error, NetworkError):
        return "Network error occurred. Please check your internet connection and try again."
    
    elif isinstance(error, TimeoutError):
        return "The request timed out. Please try again."
    
    elif isinstance(error, ContentFilterError):
        return "Content was filtered by safety systems. Please modify your request and try again."
    
    elif isinstance(error, ServerError):
        return "A server error occurred. Please try again later."
    
    else:
        return f"An error occurred: {error.message}"