"""
Token counting and chat compression for My CLI.

This module provides token management, counting, and conversation compression
functionality matching the original Gemini CLI's approach.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from .turn import Message, MessageRole, Turn
from .errors import GeminiError, TokenLimitExceededError, classify_error

logger = logging.getLogger(__name__)


class CompressionStrategy(Enum):
    """Strategies for compressing conversation history."""
    TRUNCATE_OLDEST = "truncate_oldest"
    SUMMARIZE_MIDDLE = "summarize_middle"
    SLIDING_WINDOW = "sliding_window"
    SEMANTIC_COMPRESSION = "semantic_compression"


@dataclass
class TokenLimits:
    """Token limits for different models."""
    input_tokens: int
    output_tokens: int
    total_tokens: int
    
    @classmethod
    def get_limits_for_model(cls, model: str) -> "TokenLimits":
        """Get token limits for a specific model."""
        # Gemini model limits (approximate)
        model_limits = {
            "gemini-2.0-flash-exp": cls(1000000, 8192, 1000000),
            "gemini-1.5-pro": cls(1000000, 8192, 1000000),
            "gemini-1.5-flash": cls(1000000, 8192, 1000000),
            "gemini-1.0-pro": cls(30720, 2048, 32768),
        }
        
        # Default limits if model not found
        return model_limits.get(model, cls(100000, 8192, 100000))


class TokenCounter:
    """Handles token counting for various content types."""
    
    def __init__(self, model: str = "gemini-2.0-flash-exp"):
        self.model = model
        self.limits = TokenLimits.get_limits_for_model(model)
        
        # Cache for token counts
        self._token_cache: Dict[str, int] = {}
    
    def count_text_tokens(self, text: str) -> int:
        """
        Count tokens in text content.
        
        This is a simplified estimation. In a full implementation,
        this would use the actual tokenizer for the model.
        """
        if not text:
            return 0
        
        # Check cache
        cache_key = f"text:{hash(text)}"
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]
        
        # Simple estimation: ~4 characters per token on average
        # This varies by language and content type
        estimated_tokens = max(1, len(text) // 4)
        
        # Account for special tokens and formatting
        # Add extra tokens for punctuation, formatting, etc.
        special_chars = len(re.findall(r'[.!?;:,\n\r\t]', text))
        estimated_tokens += special_chars // 4
        
        # Cache the result
        self._token_cache[cache_key] = estimated_tokens
        return estimated_tokens
    
    def count_message_tokens(self, message: Message) -> int:
        """Count tokens in a message."""
        total_tokens = 0
        
        # Role token (each message has role overhead)
        total_tokens += 3  # Approximate overhead for role and structure
        
        for part in message.parts:
            if part.text:
                total_tokens += self.count_text_tokens(part.text)
            elif part.function_call:
                # Function calls have additional structure overhead
                total_tokens += 10  # Base overhead
                if part.function_call.get("name"):
                    total_tokens += self.count_text_tokens(part.function_call["name"])
                if part.function_call.get("args"):
                    # JSON serialization of args
                    import json
                    args_text = json.dumps(part.function_call["args"])
                    total_tokens += self.count_text_tokens(args_text)
            elif part.function_response:
                # Function responses
                total_tokens += 5  # Base overhead
                if part.function_response.get("response"):
                    import json
                    response_text = json.dumps(part.function_response["response"])
                    total_tokens += self.count_text_tokens(response_text)
            elif part.inline_data or part.file_data:
                # Media content - estimate based on type and size
                total_tokens += 100  # Base estimate for media
        
        return total_tokens
    
    def count_messages_tokens(self, messages: List[Message]) -> int:
        """Count total tokens in a list of messages."""
        return sum(self.count_message_tokens(msg) for msg in messages)
    
    def count_turn_tokens(self, turn: Turn) -> int:
        """Count tokens in a turn."""
        return self.count_messages_tokens(turn.messages)
    
    def estimate_response_tokens(
        self,
        prompt_tokens: int,
        max_output_tokens: Optional[int] = None
    ) -> int:
        """Estimate tokens that will be used for a response."""
        # Use configured max or model limit
        max_tokens = max_output_tokens or self.limits.output_tokens
        
        # Conservative estimate: use 80% of available tokens
        available_tokens = self.limits.total_tokens - prompt_tokens
        return min(max_tokens, int(available_tokens * 0.8))
    
    def check_token_limits(
        self,
        messages: List[Message],
        estimated_response_tokens: Optional[int] = None
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if messages fit within token limits.
        
        Returns:
            (within_limits, token_info)
        """
        prompt_tokens = self.count_messages_tokens(messages)
        response_tokens = estimated_response_tokens or self.estimate_response_tokens(prompt_tokens)
        total_tokens = prompt_tokens + response_tokens
        
        token_info = {
            "prompt_tokens": prompt_tokens,
            "estimated_response_tokens": response_tokens,
            "total_tokens": total_tokens,
            "limit_total": self.limits.total_tokens,
            "limit_input": self.limits.input_tokens,
            "limit_output": self.limits.output_tokens,
            "within_limits": total_tokens <= self.limits.total_tokens and prompt_tokens <= self.limits.input_tokens
        }
        
        return token_info["within_limits"], token_info
    
    def clear_cache(self):
        """Clear the token counting cache."""
        self._token_cache.clear()


class ConversationCompressor:
    """Handles conversation compression to fit within token limits."""
    
    def __init__(
        self,
        token_counter: TokenCounter,
        strategy: CompressionStrategy = CompressionStrategy.SLIDING_WINDOW
    ):
        self.token_counter = token_counter
        self.strategy = strategy
        self.compression_stats = {
            "compressions_performed": 0,
            "tokens_saved": 0,
            "messages_removed": 0,
            "messages_summarized": 0,
        }
    
    async def compress_conversation(
        self,
        messages: List[Message],
        target_tokens: Optional[int] = None,
        preserve_recent: int = 3
    ) -> Tuple[List[Message], Dict[str, Any]]:
        """
        Compress conversation to fit within token limits.
        
        Args:
            messages: List of messages to compress
            target_tokens: Target token count (uses model limit if not provided)
            preserve_recent: Number of recent message pairs to always preserve
            
        Returns:
            (compressed_messages, compression_info)
        """
        if not messages:
            return messages, {"compression_performed": False}
        
        # Calculate current token usage
        current_tokens = self.token_counter.count_messages_tokens(messages)
        target = target_tokens or int(self.token_counter.limits.input_tokens * 0.8)
        
        if current_tokens <= target:
            return messages, {"compression_performed": False, "current_tokens": current_tokens}
        
        logger.info(f"Compressing conversation: {current_tokens} -> {target} tokens")
        
        # Apply compression strategy
        if self.strategy == CompressionStrategy.TRUNCATE_OLDEST:
            compressed_messages = await self._truncate_oldest(messages, target, preserve_recent)
        elif self.strategy == CompressionStrategy.SLIDING_WINDOW:
            compressed_messages = await self._sliding_window(messages, target, preserve_recent)
        elif self.strategy == CompressionStrategy.SUMMARIZE_MIDDLE:
            compressed_messages = await self._summarize_middle(messages, target, preserve_recent)
        else:
            # Default to sliding window
            compressed_messages = await self._sliding_window(messages, target, preserve_recent)
        
        # Calculate compression results
        new_tokens = self.token_counter.count_messages_tokens(compressed_messages)
        tokens_saved = current_tokens - new_tokens
        messages_removed = len(messages) - len(compressed_messages)
        
        # Update stats
        self.compression_stats["compressions_performed"] += 1
        self.compression_stats["tokens_saved"] += tokens_saved
        self.compression_stats["messages_removed"] += messages_removed
        
        compression_info = {
            "compression_performed": True,
            "strategy": self.strategy.value,
            "original_tokens": current_tokens,
            "compressed_tokens": new_tokens,
            "tokens_saved": tokens_saved,
            "original_messages": len(messages),
            "compressed_messages": len(compressed_messages),
            "messages_removed": messages_removed,
            "compression_ratio": new_tokens / current_tokens if current_tokens > 0 else 1.0
        }
        
        logger.info(f"Compression completed: {compression_info}")
        return compressed_messages, compression_info
    
    async def _truncate_oldest(
        self,
        messages: List[Message],
        target_tokens: int,
        preserve_recent: int
    ) -> List[Message]:
        """Compress by removing oldest messages."""
        if len(messages) <= preserve_recent * 2:
            return messages
        
        # Always preserve the most recent messages
        preserved_messages = messages[-(preserve_recent * 2):]
        
        # Try adding older messages until we hit the token limit
        result_messages = []
        available_tokens = target_tokens - self.token_counter.count_messages_tokens(preserved_messages)
        
        for message in reversed(messages[:-(preserve_recent * 2)]):
            message_tokens = self.token_counter.count_message_tokens(message)
            if available_tokens >= message_tokens:
                result_messages.insert(0, message)
                available_tokens -= message_tokens
            else:
                break
        
        return result_messages + preserved_messages
    
    async def _sliding_window(
        self,
        messages: List[Message],
        target_tokens: int,
        preserve_recent: int
    ) -> List[Message]:
        """Compress using a sliding window approach."""
        if len(messages) <= preserve_recent * 2:
            return messages
        
        # Keep the most recent messages that fit within the limit
        result_messages = []
        current_tokens = 0
        
        # Start from the end and work backwards
        for message in reversed(messages):
            message_tokens = self.token_counter.count_message_tokens(message)
            if current_tokens + message_tokens <= target_tokens:
                result_messages.insert(0, message)
                current_tokens += message_tokens
            else:
                # Stop adding older messages
                break
        
        return result_messages
    
    async def _summarize_middle(
        self,
        messages: List[Message],
        target_tokens: int,
        preserve_recent: int
    ) -> List[Message]:
        """Compress by summarizing middle conversations."""
        if len(messages) <= preserve_recent * 4:
            return await self._sliding_window(messages, target_tokens, preserve_recent)
        
        # Keep first few and last few messages, summarize the middle
        keep_start = preserve_recent
        keep_end = preserve_recent
        
        start_messages = messages[:keep_start]
        end_messages = messages[-keep_end:]
        middle_messages = messages[keep_start:-keep_end]
        
        # For now, just truncate the middle (in a full implementation,
        # this would generate a summary of the middle conversation)
        middle_summary = self._create_simple_summary(middle_messages)
        
        # Calculate tokens
        start_tokens = self.token_counter.count_messages_tokens(start_messages)
        end_tokens = self.token_counter.count_messages_tokens(end_messages)
        summary_tokens = self.token_counter.count_message_tokens(middle_summary)
        
        if start_tokens + end_tokens + summary_tokens <= target_tokens:
            return start_messages + [middle_summary] + end_messages
        else:
            # Fall back to sliding window
            return await self._sliding_window(messages, target_tokens, preserve_recent)
    
    def _create_simple_summary(self, messages: List[Message]) -> Message:
        """Create a simple summary message for a list of messages."""
        if not messages:
            return Message.create_text_message(MessageRole.SYSTEM, "[Empty conversation section]")
        
        # Count messages by role
        user_count = len([m for m in messages if m.role == MessageRole.USER])
        model_count = len([m for m in messages if m.role == MessageRole.MODEL])
        tool_count = len([m for m in messages if m.role == MessageRole.TOOL])
        
        # Create summary text
        summary_parts = []
        if user_count > 0:
            summary_parts.append(f"{user_count} user message{'s' if user_count != 1 else ''}")
        if model_count > 0:
            summary_parts.append(f"{model_count} model response{'s' if model_count != 1 else ''}")
        if tool_count > 0:
            summary_parts.append(f"{tool_count} tool execution{'s' if tool_count != 1 else ''}")
        
        summary_text = f"[Conversation summary: {', '.join(summary_parts)} - {len(messages)} total messages]"
        
        return Message.create_text_message(MessageRole.SYSTEM, summary_text)
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return self.compression_stats.copy()
    
    def reset_stats(self):
        """Reset compression statistics."""
        self.compression_stats = {
            "compressions_performed": 0,
            "tokens_saved": 0,
            "messages_removed": 0,
            "messages_summarized": 0,
        }


class TokenManager:
    """Main token management coordinator."""
    
    def __init__(
        self,
        model: str = "gemini-2.0-flash-exp",
        compression_strategy: CompressionStrategy = CompressionStrategy.SLIDING_WINDOW,
        auto_compress_threshold: float = 0.8
    ):
        self.model = model
        self.auto_compress_threshold = auto_compress_threshold
        
        self.token_counter = TokenCounter(model)
        self.compressor = ConversationCompressor(self.token_counter, compression_strategy)
        
        # Statistics
        self.stats = {
            "total_tokens_counted": 0,
            "total_compressions": 0,
            "total_tokens_saved": 0,
        }
    
    async def prepare_messages_for_generation(
        self,
        messages: List[Message],
        max_output_tokens: Optional[int] = None,
        auto_compress: bool = True
    ) -> Tuple[List[Message], Dict[str, Any]]:
        """
        Prepare messages for generation, compressing if necessary.
        
        Args:
            messages: Messages to prepare
            max_output_tokens: Maximum tokens for response
            auto_compress: Whether to automatically compress if needed
            
        Returns:
            (prepared_messages, preparation_info)
        """
        preparation_info = {
            "compression_performed": False,
            "within_limits": True,
            "token_info": {},
            "compression_info": {}
        }
        
        # Check token limits
        within_limits, token_info = self.token_counter.check_token_limits(
            messages, max_output_tokens
        )
        preparation_info["token_info"] = token_info
        preparation_info["within_limits"] = within_limits
        
        # Update stats
        self.stats["total_tokens_counted"] += token_info["prompt_tokens"]
        
        if not within_limits and auto_compress:
            # Calculate target tokens (leave room for response)
            response_tokens = max_output_tokens or self.token_counter.limits.output_tokens
            target_tokens = int(
                (self.token_counter.limits.total_tokens - response_tokens) * self.auto_compress_threshold
            )
            
            # Compress conversation
            compressed_messages, compression_info = await self.compressor.compress_conversation(
                messages, target_tokens
            )
            
            preparation_info["compression_performed"] = True
            preparation_info["compression_info"] = compression_info
            
            # Update stats
            if compression_info.get("compression_performed"):
                self.stats["total_compressions"] += 1
                self.stats["total_tokens_saved"] += compression_info.get("tokens_saved", 0)
            
            return compressed_messages, preparation_info
        elif not within_limits:
            # Compression disabled but messages don't fit
            raise TokenLimitExceededError(
                f"Messages exceed token limit: {token_info['total_tokens']} > {token_info['limit_total']}",
                current_tokens=token_info["total_tokens"],
                max_tokens=token_info["limit_total"]
            )
        
        return messages, preparation_info
    
    def count_tokens(self, content: Union[str, Message, List[Message]]) -> int:
        """Count tokens in various content types."""
        if isinstance(content, str):
            return self.token_counter.count_text_tokens(content)
        elif isinstance(content, Message):
            return self.token_counter.count_message_tokens(content)
        elif isinstance(content, list):
            return self.token_counter.count_messages_tokens(content)
        else:
            raise ValueError(f"Unsupported content type: {type(content)}")
    
    def get_token_limits(self) -> TokenLimits:
        """Get token limits for the current model."""
        return self.token_counter.limits
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get token management statistics."""
        return {
            "model": self.model,
            "token_limits": {
                "input_tokens": self.token_counter.limits.input_tokens,
                "output_tokens": self.token_counter.limits.output_tokens,
                "total_tokens": self.token_counter.limits.total_tokens,
            },
            "manager_stats": self.stats.copy(),
            "compression_stats": self.compressor.get_compression_stats(),
        }
    
    def reset_statistics(self):
        """Reset all statistics."""
        self.stats = {
            "total_tokens_counted": 0,
            "total_compressions": 0,
            "total_tokens_saved": 0,
        }
        self.compressor.reset_stats()
    
    def clear_caches(self):
        """Clear all internal caches."""
        self.token_counter.clear_cache()


# Factory functions

def create_token_manager(
    model: str = "gemini-2.0-flash-exp",
    compression_strategy: CompressionStrategy = CompressionStrategy.SLIDING_WINDOW,
    **kwargs
) -> TokenManager:
    """Create a token manager with the given configuration."""
    return TokenManager(
        model=model,
        compression_strategy=compression_strategy,
        **kwargs
    )