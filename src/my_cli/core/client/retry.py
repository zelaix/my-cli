"""
Exponential backoff retry system for My CLI API client.

This module provides sophisticated retry logic with exponential backoff,
jitter, and intelligent error classification, matching the original 
Gemini CLI's retry behavior.
"""

import asyncio
import random
import time
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar, Union
from dataclasses import dataclass
from enum import Enum
import logging

from .errors import (
    GeminiError,
    QuotaExceededError,
    ServerError,
    NetworkError,
    TimeoutError,
    RetryableError,
    is_retryable_error,
    get_retry_delay,
    classify_error,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    FIXED_DELAY = "fixed_delay"
    LINEAR_BACKOFF = "linear_backoff"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 5
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    jitter_range: float = 0.1  # ±10% jitter
    backoff_multiplier: float = 2.0
    respect_retry_after: bool = True
    
    # Quota handling
    enable_model_fallback: bool = True
    fallback_model: Optional[str] = "gemini-2.0-flash-exp"
    
    # Custom retry conditions
    should_retry_func: Optional[Callable[[Exception], bool]] = None
    on_retry_func: Optional[Callable[[Exception, int], Awaitable[None]]] = None
    on_fallback_func: Optional[Callable[[str, str], Awaitable[bool]]] = None


class RetryStats:
    """Statistics about retry attempts."""
    
    def __init__(self):
        self.total_attempts = 0
        self.successful_attempts = 0
        self.failed_attempts = 0
        self.total_delay_ms = 0
        self.error_counts: Dict[str, int] = {}
        self.fallback_used = False
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def record_attempt(self, error: Optional[Exception] = None):
        """Record a retry attempt."""
        if self.start_time is None:
            self.start_time = time.time()
        
        self.total_attempts += 1
        if error:
            self.failed_attempts += 1
            error_type = type(error).__name__
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        else:
            self.successful_attempts += 1
            self.end_time = time.time()
    
    def record_delay(self, delay_ms: int):
        """Record delay time."""
        self.total_delay_ms += delay_ms
    
    def record_fallback(self):
        """Record that fallback was used."""
        self.fallback_used = True
    
    @property
    def total_duration_ms(self) -> float:
        """Get total duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "total_delay_ms": self.total_delay_ms,
            "total_duration_ms": self.total_duration_ms,
            "error_counts": self.error_counts.copy(),
            "fallback_used": self.fallback_used,
        }


class RetryManager:
    """Manages retry logic with exponential backoff and intelligent error handling."""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._current_model: Optional[str] = None
    
    async def retry(
        self,
        func: Callable[[], Awaitable[T]],
        *,
        model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> T:
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Async function to retry
            model: Current model being used (for fallback)
            context: Additional context for retry decisions
            
        Returns:
            Result of the function call
            
        Raises:
            Last exception encountered if all retries fail
        """
        stats = RetryStats()
        self._current_model = model
        last_exception: Optional[Exception] = None
        current_delay = self.config.initial_delay_ms
        consecutive_429_count = 0
        
        for attempt in range(self.config.max_attempts):
            try:
                result = await func()
                stats.record_attempt()
                
                if attempt > 0:
                    logger.info(f"Succeeded after {attempt + 1} attempts. Stats: {stats.to_dict()}")
                
                return result
                
            except Exception as e:
                last_exception = e
                stats.record_attempt(e)
                
                # Classify the error
                gemini_error = classify_error(e)
                
                # Log the attempt
                logger.warning(
                    f"Attempt {attempt + 1}/{self.config.max_attempts} failed: {gemini_error}",
                    extra={"error_type": type(gemini_error).__name__, "attempt": attempt + 1}
                )
                
                # Check if we should retry
                if not self._should_retry(gemini_error, attempt):
                    logger.error(f"Not retrying after {attempt + 1} attempts: {gemini_error}")
                    raise gemini_error
                
                # Handle quota errors with potential fallback
                if isinstance(gemini_error, QuotaExceededError):
                    consecutive_429_count += 1
                    
                    # Try fallback for persistent quota errors
                    if (consecutive_429_count >= 2 and 
                        self.config.enable_model_fallback and 
                        self._current_model and 
                        self.config.fallback_model and
                        self._current_model != self.config.fallback_model):
                        
                        fallback_accepted = await self._try_fallback(
                            self._current_model, 
                            self.config.fallback_model,
                            gemini_error
                        )
                        
                        if fallback_accepted:
                            stats.record_fallback()
                            consecutive_429_count = 0  # Reset counter
                            current_delay = self.config.initial_delay_ms  # Reset delay
                            continue
                else:
                    consecutive_429_count = 0
                
                # Calculate delay
                delay_ms = self._calculate_delay(gemini_error, current_delay, attempt)
                
                if delay_ms > 0:
                    stats.record_delay(delay_ms)
                    logger.info(f"Waiting {delay_ms}ms before retry {attempt + 2}")
                    await asyncio.sleep(delay_ms / 1000.0)
                
                # Update delay for next iteration
                current_delay = self._update_delay(current_delay)
                
                # Call retry callback if configured
                if self.config.on_retry_func:
                    try:
                        await self.config.on_retry_func(gemini_error, attempt + 1)
                    except Exception as callback_error:
                        logger.error(f"Error in retry callback: {callback_error}")
        
        # All retries exhausted
        logger.error(f"All {self.config.max_attempts} retry attempts failed. Final stats: {stats.to_dict()}")
        if last_exception:
            raise classify_error(last_exception)
        else:
            raise GeminiError("All retry attempts failed with no recorded error")
    
    def _should_retry(self, error: GeminiError, attempt: int) -> bool:
        """Determine if an error should be retried."""
        # Check if we've exceeded max attempts
        if attempt >= self.config.max_attempts - 1:
            return False
        
        # Use custom retry function if provided
        if self.config.should_retry_func:
            try:
                return self.config.should_retry_func(error)
            except Exception as e:
                logger.error(f"Error in custom should_retry function: {e}")
        
        # Default retry logic
        return is_retryable_error(error)
    
    def _calculate_delay(self, error: GeminiError, current_delay: int, attempt: int) -> int:
        """Calculate delay for next retry attempt."""
        # Check for explicit retry delay in error
        if self.config.respect_retry_after:
            retry_after = get_retry_delay(error)
            if retry_after:
                return retry_after * 1000  # Convert to milliseconds
        
        # Use configured strategy
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.initial_delay_ms
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.initial_delay_ms * (attempt + 1)
        else:  # EXPONENTIAL_BACKOFF (default)
            delay = current_delay
        
        # Apply jitter if enabled
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = int(delay + jitter)
        
        # Ensure delay is within bounds
        delay = max(0, min(delay, self.config.max_delay_ms))
        
        return delay
    
    def _update_delay(self, current_delay: int) -> int:
        """Update delay for next iteration."""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            return min(
                int(current_delay * self.config.backoff_multiplier),
                self.config.max_delay_ms
            )
        return current_delay
    
    async def _try_fallback(
        self, 
        current_model: str, 
        fallback_model: str, 
        error: GeminiError
    ) -> bool:
        """
        Try to fallback to a different model.
        
        Args:
            current_model: Current model that failed
            fallback_model: Model to fallback to
            error: The error that triggered fallback
            
        Returns:
            True if fallback was accepted and model was switched
        """
        if not self.config.on_fallback_func:
            # No fallback handler, auto-accept fallback
            logger.info(f"Auto-falling back from {current_model} to {fallback_model} due to quota error")
            self._current_model = fallback_model
            return True
        
        try:
            accepted = await self.config.on_fallback_func(current_model, fallback_model)
            if accepted:
                logger.info(f"Fallback accepted: switching from {current_model} to {fallback_model}")
                self._current_model = fallback_model
                return True
            else:
                logger.info(f"Fallback declined: staying with {current_model}")
                return False
        except Exception as e:
            logger.error(f"Error in fallback callback: {e}")
            return False


# Convenience functions

async def retry_with_backoff(
    func: Callable[[], Awaitable[T]],
    config: Optional[RetryConfig] = None,
    **kwargs
) -> T:
    """
    Convenience function for retrying with exponential backoff.
    
    Args:
        func: Async function to retry
        config: Retry configuration
        **kwargs: Additional arguments for retry
        
    Returns:
        Result of the function call
    """
    manager = RetryManager(config)
    return await manager.retry(func, **kwargs)


def create_default_retry_config(
    max_attempts: int = 5,
    initial_delay_ms: int = 1000,
    max_delay_ms: int = 30000,
    enable_model_fallback: bool = True
) -> RetryConfig:
    """Create a default retry configuration."""
    return RetryConfig(
        max_attempts=max_attempts,
        initial_delay_ms=initial_delay_ms,
        max_delay_ms=max_delay_ms,
        enable_model_fallback=enable_model_fallback,
    )


def create_aggressive_retry_config() -> RetryConfig:
    """Create an aggressive retry configuration for critical operations."""
    return RetryConfig(
        max_attempts=10,
        initial_delay_ms=500,
        max_delay_ms=60000,
        backoff_multiplier=1.5,
        jitter_range=0.2,
        enable_model_fallback=True,
    )


def create_conservative_retry_config() -> RetryConfig:
    """Create a conservative retry configuration for non-critical operations."""
    return RetryConfig(
        max_attempts=3,
        initial_delay_ms=2000,
        max_delay_ms=10000,
        backoff_multiplier=3.0,
        jitter_range=0.05,
        enable_model_fallback=False,
    )